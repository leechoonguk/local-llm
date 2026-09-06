"""Batch job tests - sync_data_go_kr_ledgers against an in-memory engine.

The gateway pages by number (the PAGE family) and has no end code; the job's
contract is the same as its 식품안전나라 sibling's - one feed, one whole pass,
one step per window, spoken in rows - so the tests are that contract in this
gateway's dialect.
"""

from __future__ import annotations

import pytest

import app.batch.sync_data_go_kr_ledgers as job
from app.core.exceptions import IntegrationError, LedgerFloorError
from app.models.food.nutrition import FoodNutrition
from app.services.batch.run import current_run_id
from tests.batch.scripted import rows, run_in_context, script_walk, steps, swapped_engine


(NUTRITION,) = (feed.operation_code for feed in job.FEEDS)


def _nutrition(index: int, **overrides: object) -> dict[str, object]:
    return {"food_code": f"D{index:06d}", "food_name": "김치", **overrides}


def _script(*pages):
    return {NUTRITION: list(pages)}


@pytest.fixture()
async def test_engine():
    """The job module's engine, swapped for an in-memory one; no run in context."""
    current_run_id.set(None)
    async with swapped_engine(job) as engine:
        yield engine


@pytest.mark.asyncio
async def test_the_feed_is_walked_by_page_number_until_a_short_page(
    test_engine, monkeypatch
) -> None:
    """Pages of PAGE_SIZE from page 1; the ledger afterwards is the pass."""
    full_page = [_nutrition(index) for index in range(1, job.PAGE_SIZE + 1)]
    asked = script_walk(monkeypatch, "PAGE", _script(full_page, [_nutrition(job.PAGE_SIZE + 1)]))

    assert await job.sync_data_go_kr_ledgers() == job.PAGE_SIZE + 1

    assert asked == [
        (NUTRITION, {"page_no": 1, "num_of_rows": job.PAGE_SIZE}),
        (NUTRITION, {"page_no": 2, "num_of_rows": job.PAGE_SIZE}),
    ]
    ledger = await rows(test_engine, FoodNutrition)
    assert len(ledger) == job.PAGE_SIZE + 1
    assert {row.created_by for row in ledger} == {job.SYNCED_BY}


@pytest.mark.asyncio
async def test_the_next_night_reads_from_page_one_and_changes_only_what_moved(
    test_engine, monkeypatch
) -> None:
    """No cursor: page 1 again, and the ledger follows the feed."""
    script_walk(monkeypatch, "PAGE", _script([_nutrition(1), _nutrition(2), _nutrition(3)]))
    await job.sync_data_go_kr_ledgers()
    ids = {row.food_code: row.id for row in await rows(test_engine, FoodNutrition)}

    # Row 1 unchanged, row 2 renamed, row 3 gone, row 4 new: three changes.
    asked = script_walk(
        monkeypatch,
        "PAGE",
        _script([_nutrition(1), _nutrition(2, food_name="묵은지"), _nutrition(4)]),
    )
    assert await job.sync_data_go_kr_ledgers() == 3
    assert asked[0][1]["page_no"] == 1
    after = {row.food_code: row for row in await rows(test_engine, FoodNutrition)}
    assert set(after) == {"D000001", "D000002", "D000004"}
    assert after["D000001"].id == ids["D000001"] and after["D000001"].version == 1
    assert after["D000002"].id == ids["D000002"] and after["D000002"].version == 2


@pytest.mark.asyncio
async def test_each_page_is_recorded_as_a_step_in_rows(test_engine, monkeypatch) -> None:
    """The step log speaks in rows whichever family the gateway pages by."""
    full_page = [_nutrition(index) for index in range(1, job.PAGE_SIZE + 1)]
    script_walk(monkeypatch, "PAGE", _script(full_page, [_nutrition(job.PAGE_SIZE + 1)]))
    await run_in_context(test_engine, "sync_data_go_kr_ledgers")

    await job.sync_data_go_kr_ledgers()

    recorded = await steps(test_engine)
    assert [(s.sequence, s.range_start, s.range_end, s.received) for s in recorded] == [
        (1, 1, job.PAGE_SIZE, job.PAGE_SIZE),
        (2, job.PAGE_SIZE + 1, 2 * job.PAGE_SIZE, 1),
    ]
    assert {s.status for s in recorded} == {"SUCCEEDED"}
    assert {s.written for s in recorded} == {None}


@pytest.mark.asyncio
async def test_a_job_started_by_hand_records_no_step(test_engine, monkeypatch) -> None:
    """A step without a run has nothing to belong to."""
    script_walk(monkeypatch, "PAGE", _script([_nutrition(1)]))
    await job.sync_data_go_kr_ledgers()
    assert await steps(test_engine) == []


@pytest.mark.asyncio
async def test_a_refusal_leaves_the_ledger_and_is_the_runs_failure(
    test_engine, monkeypatch
) -> None:
    """Yesterday's ledger stands, the refused window is a FAILED step, the run fails."""
    script_walk(monkeypatch, "PAGE", _script([_nutrition(1), _nutrition(2)]))
    await job.sync_data_go_kr_ledgers()

    refusal = IntegrationError(
        job.PROVIDER_CODE, NUTRITION, "External API error: HTTP 503", status_code=503
    )
    full_page = [_nutrition(index) for index in range(1, job.PAGE_SIZE + 1)]
    script_walk(monkeypatch, "PAGE", _script(full_page, refusal))
    await run_in_context(test_engine, "sync_data_go_kr_ledgers")

    with pytest.raises(IntegrationError, match="HTTP 503"):
        await job.sync_data_go_kr_ledgers()

    assert len(await rows(test_engine, FoodNutrition)) == 2
    failed = [s for s in await steps(test_engine) if s.status == "FAILED"]
    assert [(s.range_start, s.range_end, s.error_code) for s in failed] == [
        (job.PAGE_SIZE + 1, 2 * job.PAGE_SIZE, "IntegrationError")
    ]


@pytest.mark.asyncio
async def test_a_pass_under_the_floor_is_a_failed_feed(test_engine, monkeypatch) -> None:
    """A gateway answering empty pages must not empty the ledger."""
    script_walk(monkeypatch, "PAGE", _script([_nutrition(1), _nutrition(2)]))
    await job.sync_data_go_kr_ledgers()

    script_walk(monkeypatch, "PAGE", _script([]))
    with pytest.raises(LedgerFloorError, match="food_nutrition"):
        await job.sync_data_go_kr_ledgers()
    assert len(await rows(test_engine, FoodNutrition)) == 2
