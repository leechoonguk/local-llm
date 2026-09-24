"""The body every ledger job shares — one walk, one ledger, one step per window."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.batch.sync_food_ledger_production as production_job
import app.batch.sync_food_ledger_recall as recall_job
import app.services.batch.ledger_feed as ledger_feed
from app.core.exceptions import IntegrationError
from app.models.batch.step import BatchStep
from app.models.food.ledger_production import FoodLedgerProduction
from app.models.food.ledger_recall import FoodLedgerRecall
from tests.batch.ledger_job import canonical_records
from tests.batch.scripted import (
    rows,
    run_in_context,
    script_segments,
    script_walk,
    steps,
    swapped_engine,
)


RECORDS = canonical_records("search-food-recall")

PRODUCTION = canonical_records("search-food-production")


@pytest.mark.asyncio
async def test_a_refused_window_is_recorded_and_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    """A refusal mid-walk ends the run, and the window it died on is a step.

    The step names the window after the last full page - the one the walk was
    asking for - because the raise carried no window of its own. The ledger is
    last week's: a pass that did not finish replaces nothing.
    """
    async with swapped_engine(ledger_feed) as engine:
        page = RECORDS * 34
        script_walk(
            monkeypatch,
            "RANGE",
            {
                "search-food-recall": [
                    page,
                    IntegrationError("mfds-food-safety-korea", "search-food-recall", "HTTP 503"),
                ]
            },
            page_size=len(page),
        )
        await run_in_context(engine, recall_job.SYNCED_BY)

        with pytest.raises(IntegrationError):
            await recall_job.sync_food_ledger_recall()

        recorded = await steps(engine)
        assert [step.sequence for step in recorded] == [1, 2]
        assert recorded[1].error_code == "IntegrationError"
        assert recorded[0].range_end is not None
        assert recorded[1].range_start == recorded[0].range_end + 1
        assert await rows(engine, FoodLedgerRecall) == []


@pytest.mark.asyncio
async def test_a_segmented_feed_walks_every_value_into_one_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """생산실적 is published per 보고년도, and the years are how the feed is addressed.

    The coordinate comes off the operation row, not the job: every year the
    provider answers for is walked from its own first window, and every page
    lands in one stage - so the ledger after the pass is the whole feed, not the
    last year of it. A year the provider answers nothing for is not walked at
    all, which is how next January's year arrives without an edit, and a year
    older than the configured first one is never asked about.
    """
    # The years are the test's own, not the fixture's: 생산실적 reads its feed
    # from a file now (revisions 291-296) and the recorded rows carry whatever
    # year the portal's file opens with. What is under test is the walk that a
    # coordinate addresses, so the rows state their year here.
    years = {"2023": 1, "2024": 1, "2025": 1}
    async with swapped_engine(ledger_feed) as engine:
        script_segments(monkeypatch, {"search-food-production": years})
        asked = script_walk(
            monkeypatch,
            "RANGE",
            {
                "search-food-production": {
                    "2024": [[PRODUCTION[0] | {"report_year": "2024"}]],
                    "2025": [[record | {"report_year": "2025"} for record in PRODUCTION]],
                }
            },
            page_size=production_job.PAGE_SIZE,
            segmentation=("report_year", ["2024", "2025", "2026"]),
        )

        written = await production_job.sync_food_ledger_production()

        assert [window.get("report_year") for _, window in asked] == ["2024", "2025"]
        assert written == len(PRODUCTION) + 1
        assert {row.report_year for row in await rows(engine, FoodLedgerProduction)} == {
            "2024",
            "2025",
        }


@pytest.mark.asyncio
async def test_a_job_run_by_hand_writes_no_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    """A step belongs to a run, and a hand-started job has none to belong to."""
    async with swapped_engine(ledger_feed) as engine:
        script_walk(monkeypatch, "RANGE", {"search-food-recall": [RECORDS]}, page_size=len(RECORDS))
        ledger_feed.current_run_id.set(None)

        assert await recall_job.sync_food_ledger_recall() == len(RECORDS)

        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            assert (await session.execute(select(BatchStep))).scalars().all() == []
