"""Batch job tests — sync_food_nutrition_ledger against an in-memory engine.

The provider is scripted: the job's contract is which pages it asks for and what
it does with the answers, not what the network returned.

This is the first ledger that pages by **page number**, so what these tests fix
is different from the row-interval siblings: the window's ceiling is refused
rather than clamped, a finished pass stays *on* its last page, and the overlap
is a whole page instead of one row.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.batch.sync_food_nutrition_ledger import MAX_PAGE_SIZE, OPERATION_CODE
from app.core.exceptions import IntegrationConfigurationError, IntegrationError
from app.core.integration import IntegrationExecutionResult
from app.models.base import Base
from app.models.batch.run import BatchRun
from app.models.batch.step import BatchStep
from app.models.food.nutrition import FoodNutrition
from app.services.batch.checkpoint import BatchCheckpointService
from app.services.batch.run import BatchRunService, current_run_id
from app.services.integration.operation import IntegrationOperationService


FOOD_CODE = "D101-004160000-000"


@pytest.fixture()
async def test_engine():
    """In-memory engine + tables, replacing the job module's engine."""
    import app.batch.sync_food_nutrition_ledger as job_module

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    original = job_module.engine
    job_module.engine = engine
    yield engine
    job_module.engine = original
    await engine.dispose()


def _record(index: int, **overrides: object) -> dict[str, object]:
    """One canonical I2790 record; `index` moves the natural key, not the content."""
    record: dict[str, object] = {
        "row_no": str(index),
        "food_code": f"{FOOD_CODE}{index}",
        "food_name": "국밥_돼지머리",
        "energy_kcal": "137.000",
        "update_date": "2025-01-23",
    }
    record.update(overrides)
    return record


def _script(monkeypatch, pages: list[list[object]]) -> list[dict[str, object]]:
    """Answer each execute_operation call with the next page; record every window."""
    windows: list[dict[str, object]] = []
    answers = iter(pages)

    async def _execute(self, provider_code, operation_code, inputs, *, actor, client=None):
        windows.append(dict(inputs))
        return (
            IntegrationExecutionResult(
                canonical_payload=list(next(answers)), metadata={}, status_code=200
            ),
            None,
        )

    monkeypatch.setattr(IntegrationOperationService, "execute_operation", _execute)
    return windows


async def _checkpoint(test_engine):
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        return await BatchCheckpointService(session).find_checkpoint(OPERATION_CODE)


@pytest.mark.asyncio
async def test_a_window_wider_than_the_provider_allows_is_refused(test_engine) -> None:
    """501 rows and up answer HTTP 200 with an empty list — the shape of the end.

    Measured (2026-09-05) at 501, 510, 550, 590, 600, 700, 750, 800, 900, 999 and
    1000. A job that asked for 1000 would import nothing, read the empty answer
    as "no more data", and report success every night. Clamping silently would
    leave the caller's wrong belief intact, so the call is never made.
    """
    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    with pytest.raises(IntegrationConfigurationError):
        await sync_food_nutrition_ledger(page_size=MAX_PAGE_SIZE + 1)


@pytest.mark.asyncio
async def test_sync_food_nutrition_ledger_pages_until_a_short_page(
    test_engine, monkeypatch
) -> None:
    """The page's own size is the only end-of-data signal this provider gives."""
    windows = _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    assert await sync_food_nutrition_ledger(page_size=2, max_pages=10) == 3
    assert [w["page_no"] for w in windows] == [1, 2]
    assert {w["num_of_rows"] for w in windows} == {2}

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        rows = list((await session.execute(select(FoodNutrition))).scalars().all())
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_a_finished_pass_stays_on_its_last_page(test_engine, monkeypatch) -> None:
    """New records are appended to the end, which is the page the pass finished on.

    A cursor one page further would step over every food added since — the
    row-interval ledgers advance past the tail because rows there have absolute
    positions; a page number does not.
    """
    _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    await sync_food_nutrition_ledger(page_size=2, max_pages=10)

    checkpoint = await _checkpoint(test_engine)
    assert checkpoint is not None
    assert (checkpoint.resume_position, checkpoint.resume_key) == (2, f"{FOOD_CODE}3")

    # The next run re-reads page 2 and picks up what was appended to it.
    windows = _script(monkeypatch, [[_record(3), _record(4)], [_record(5)]])
    assert await sync_food_nutrition_ledger(page_size=2, max_pages=10) == 2
    assert [w["page_no"] for w in windows] == [2, 3]


@pytest.mark.asyncio
async def test_an_interrupted_pass_resumes_on_the_page_it_imported(
    test_engine, monkeypatch
) -> None:
    """A 319k-record load spans runs, and the second must not start over.

    The cursor names the page the run *imported*, not the one after it: that
    page is the overlap the next run verifies its position with, and re-reading
    it writes nothing because the ledger compares before it writes.
    """
    _script(monkeypatch, [[_record(1)], [_record(2)]])

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    assert await sync_food_nutrition_ledger(page_size=1, max_pages=2) == 2

    checkpoint = await _checkpoint(test_engine)
    assert checkpoint is not None
    assert (checkpoint.resume_position, checkpoint.resume_key) == (2, f"{FOOD_CODE}2")

    # The cursor page (2) is re-read first, then the walk continues at 3.
    windows = _script(monkeypatch, [[_record(2)], [_record(3)], [_record(4)]])
    assert await sync_food_nutrition_ledger(page_size=1, max_pages=3) == 2
    assert [w["page_no"] for w in windows] == [2, 3, 4]


@pytest.mark.asyncio
async def test_a_shifted_feed_sends_the_walk_back_to_page_one(test_engine, monkeypatch) -> None:
    """Records were removed, so every later page holds different foods now.

    Left alone the cursor would keep asking for positions that moved, and every
    later run would import the wrong pages — silently, because the provider
    answers 200 either way. The last record of the overlap page is what says
    which happened.
    """
    _script(monkeypatch, [[_record(1)], [_record(2)]])

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    await sync_food_nutrition_ledger(page_size=1, max_pages=2)

    windows = _script(monkeypatch, [[_record(9)], [_record(8)], [_record(7)]])
    await sync_food_nutrition_ledger(page_size=1, max_pages=3)

    assert [w["page_no"] for w in windows] == [2, 1, 2]


@pytest.mark.asyncio
async def test_a_page_that_is_gone_restarts_the_walk(test_engine, monkeypatch) -> None:
    """The resumed page answers empty: the feed is now shorter than the cursor.

    Without the restart the cursor would sit past an end that moved and answer
    empty forever, reporting a successful nightly run that read nothing. This is
    the *resumed* page being empty - an empty page after one this run filled is
    the ordinary end of a feed, and is not this case.
    """
    _script(monkeypatch, [[_record(1)], [_record(2)]])

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    await sync_food_nutrition_ledger(page_size=1, max_pages=2)

    windows = _script(monkeypatch, [[], [_record(1)]])
    await sync_food_nutrition_ledger(page_size=1, max_pages=2)

    assert [w["page_no"] for w in windows] == [2, 1]
    checkpoint = await _checkpoint(test_engine)
    assert checkpoint is not None
    assert (checkpoint.resume_position, checkpoint.resume_key) == (1, f"{FOOD_CODE}1")


@pytest.mark.asyncio
async def test_sync_food_nutrition_ledger_stops_at_the_page_ceiling(
    test_engine, monkeypatch
) -> None:
    """A provider that never shortens a page must not be walked forever."""
    windows = _script(monkeypatch, [[_record(1)], [_record(2)], [_record(3)]])

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    assert await sync_food_nutrition_ledger(page_size=1, max_pages=2) == 2
    assert len(windows) == 2


async def _run_in_context(test_engine) -> None:
    """Open a run and put it in context, the way the scheduler does."""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        run = await BatchRunService(session).create_started_run(
            None, "sync_food_nutrition_ledger", "CRON", "scheduler"
        )
    current_run_id.set(run.id)


async def _steps(test_engine) -> list[BatchStep]:
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        return list(
            (await session.execute(select(BatchStep).order_by(BatchStep.sequence))).scalars().all()
        )


@pytest.mark.asyncio
async def test_each_page_is_recorded_as_a_step_in_rows(test_engine, monkeypatch) -> None:
    """The step log speaks in rows, so two ledgers' runs compare in one unit.

    The call asks for `page_no`; the step records the rows that page covers.
    Reading `page 2` in a log beside a sibling's `rows 1001-2000` would make
    "how far did the night get" two different questions.
    """
    _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])
    await _run_in_context(test_engine)

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    await sync_food_nutrition_ledger(page_size=2, max_pages=10)

    steps = await _steps(test_engine)
    assert [(s.sequence, s.range_start, s.range_end) for s in steps] == [(1, 1, 2), (2, 3, 4)]
    assert [(s.status, s.received, s.written) for s in steps] == [
        ("SUCCEEDED", 2, 2),
        ("SUCCEEDED", 1, 1),
    ]


@pytest.mark.asyncio
async def test_a_failing_page_is_recorded_before_the_job_dies(test_engine, monkeypatch) -> None:
    """The page that failed is the one worth naming."""
    calls = {"n": 0}

    async def _execute(self, provider_code, operation_code, inputs, *, actor, client=None):
        calls["n"] += 1
        if calls["n"] == 2:
            raise IntegrationError(provider_code, operation_code, "External API error: HTTP 503")
        return (
            IntegrationExecutionResult(
                canonical_payload=[_record(calls["n"])], metadata={}, status_code=200
            ),
            None,
        )

    monkeypatch.setattr(IntegrationOperationService, "execute_operation", _execute)
    await _run_in_context(test_engine)

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    with pytest.raises(IntegrationError):
        await sync_food_nutrition_ledger(page_size=1, max_pages=3)

    steps = await _steps(test_engine)
    assert [(step.sequence, step.status) for step in steps] == [(1, "SUCCEEDED"), (2, "FAILED")]
    assert steps[1].error_code == "IntegrationError"
    assert steps[1].range_start == 2


@pytest.mark.asyncio
async def test_a_job_run_by_hand_records_no_steps(test_engine, monkeypatch) -> None:
    """A step without a run has nothing to belong to."""
    _script(monkeypatch, [[_record(1)]])
    current_run_id.set(None)

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    assert await sync_food_nutrition_ledger(page_size=2, max_pages=10) == 1

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        assert (await session.execute(select(BatchRun))).scalars().all() == []
    assert await _steps(test_engine) == []


@pytest.mark.asyncio
async def test_a_one_record_page_arrives_as_a_bare_object(test_engine, monkeypatch) -> None:
    """The provider drops the list when a page holds exactly one record."""
    answers = iter([_record(1), []])

    async def _execute(self, provider_code, operation_code, inputs, *, actor, client=None):
        return (
            IntegrationExecutionResult(
                canonical_payload=next(answers), metadata={}, status_code=200
            ),
            None,
        )

    monkeypatch.setattr(IntegrationOperationService, "execute_operation", _execute)

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    assert await sync_food_nutrition_ledger(page_size=2, max_pages=3) == 1


@pytest.mark.asyncio
async def test_a_page_whose_first_record_carries_no_key_stores_no_anchor(
    test_engine, monkeypatch
) -> None:
    """An anchor the ledger could not store is not a position to resume from.

    The portal sends sparse records, and a page can open with one: a string
    where an object was expected, or an object with no `food_code`. Storing
    either as the anchor would make the next run compare against a key no
    record can ever match and restart the 319k walk every night.
    """
    _script(monkeypatch, [["not-a-record"]])

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    assert await sync_food_nutrition_ledger(page_size=2, max_pages=2) == 0

    checkpoint = await _checkpoint(test_engine)
    assert checkpoint is not None
    assert checkpoint.resume_key is None

    _script(monkeypatch, [[{"food_name": "국밥"}]])
    assert await sync_food_nutrition_ledger(page_size=2, max_pages=2) == 0

    checkpoint = await _checkpoint(test_engine)
    assert checkpoint is not None
    assert checkpoint.resume_key is None


@pytest.mark.asyncio
async def test_an_empty_first_page_leaves_the_walk_where_it_started(
    test_engine, monkeypatch
) -> None:
    """Page 1 with no records is a feed that answered nothing, not an error.

    It is also what this provider returns for a window it refuses, which is why
    `MAX_PAGE_SIZE` is checked before the call - here the page is honest, and
    the run has to end on it without a key to anchor.
    """
    _script(monkeypatch, [[]])

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    assert await sync_food_nutrition_ledger(page_size=2, max_pages=2) == 0

    checkpoint = await _checkpoint(test_engine)
    assert checkpoint is not None
    assert (checkpoint.resume_position, checkpoint.resume_key) == (1, None)


@pytest.mark.asyncio
async def test_a_feed_that_ends_on_a_full_page_is_not_a_shifted_feed(
    test_engine, monkeypatch
) -> None:
    """A full last page is followed by an empty one, and that empty page is the end.

    319,060 % 500 = 60 today; 440 more foods and the last page is exactly full.
    Read as "the feed is shorter than the cursor", the empty page would send the
    walk back to page 1 *inside the same run*, re-walk the whole set until the
    ceiling, and do it again every night - a nightly 639-call pass that writes
    nothing, reported as success.
    """
    windows = _script(monkeypatch, [[_record(1), _record(2)], [_record(3), _record(4)], []])

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    assert await sync_food_nutrition_ledger(page_size=2, max_pages=10) == 4
    assert [w["page_no"] for w in windows] == [1, 2, 3]

    # The run resumes on the last page that held records, anchored on it.
    checkpoint = await _checkpoint(test_engine)
    assert checkpoint is not None
    assert (checkpoint.resume_position, checkpoint.resume_key) == (2, f"{FOOD_CODE}3")


@pytest.mark.asyncio
async def test_a_changed_page_size_is_caught_by_the_anchor(test_engine, monkeypatch) -> None:
    """A page number only means a position under the size it was written with.

    Page 2 of a 2-row walk and page 2 of a 3-row walk start at different
    records. The checkpoint stores no page size, on purpose - the anchor is what
    notices: the resumed page's first record is not the one recorded, so the walk
    restarts and pays one full pass instead of silently importing from the wrong
    offset for as long as the setting stays changed.
    """
    _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])

    from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger

    await sync_food_nutrition_ledger(page_size=2, max_pages=10)

    windows = _script(
        monkeypatch,
        [
            [_record(4), _record(5), _record(6)],
            [_record(1), _record(2), _record(3)],
            [_record(4), _record(5), _record(6)],
            [],
        ],
    )
    assert await sync_food_nutrition_ledger(page_size=3, max_pages=10) == 3
    assert [w["page_no"] for w in windows] == [2, 1, 2, 3]
