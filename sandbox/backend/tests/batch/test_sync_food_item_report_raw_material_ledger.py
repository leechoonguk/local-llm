"""Batch job tests — sync_food_item_report_raw_material_ledger against an in-memory engine.

The provider is scripted: the job's contract is what it writes and how it
resumes, not what the network answered.
"""

from collections.abc import Mapping

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.batch.sync_food_item_report_raw_material_ledger import OPERATION_CODE
from app.core.exceptions import IntegrationError
from app.core.integration import IntegrationExecutionResult
from app.models.base import Base
from app.models.batch.run import BatchRun
from app.models.batch.step import BatchStep
from app.models.food.item_report_raw_material import FoodItemReportRawMaterial
from app.services.batch.checkpoint import BatchCheckpointService
from app.services.batch.run import BatchRunService, current_run_id
from app.services.integration.operation import IntegrationOperationService


ITEM_REPORT_NO = "199704010552"


@pytest.fixture()
async def test_engine():
    """In-memory engine + tables, replacing the job module's engine."""
    import app.batch.sync_food_item_report_raw_material_ledger as job_module

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
    """One canonical C002 record; `index` moves the natural key, not the content."""
    record: dict[str, object] = {
        "item_report_no": f"{ITEM_REPORT_NO}{index}",
        "product_name": "가시오가피 냉면",
        "changed_date": "20230610",
    }
    record.update(overrides)
    return record


def _refusing_script(monkeypatch, pages: list[list[object]], envelope_value: str) -> None:
    """Answer the pages, then refuse the way an operation that rejects the code does.

    The sibling feeds differ only in whether their contract lists the no-data
    code among the envelope's accepted values: one gets an empty page, the other
    a refusal carrying the same code. The job must read both as the end.
    """
    answers = iter(pages)

    async def _execute(self, provider_code, operation_code, inputs, *, actor, client=None):
        try:
            page = next(answers)
        except StopIteration:
            raise IntegrationError(
                provider_code,
                operation_code,
                f"External API refused the request: result_code={envelope_value} "
                "(expected INFO-000)",
                envelope_key="result_code",
                envelope_value=envelope_value,
            ) from None
        return (
            IntegrationExecutionResult(canonical_payload=list(page), metadata={}, status_code=200),
            None,
        )

    monkeypatch.setattr(IntegrationOperationService, "execute_operation", _execute)


def _script(monkeypatch, pages: list[list[object]]) -> list[Mapping[str, object]]:
    """Answer each execute_operation call with the next page; record every window.

    The provider is scripted rather than mocked at the transport: the job's
    contract is the sequence of windows it asks for and what it does with the
    answers, and `IntegrationOperationService` is the seam it talks through.

    No `total_count` is scripted, because the job reads none: some operations on
    this portal report a fixed `1` whatever the set holds, so the end of a feed
    is a short page and nothing else.
    """
    windows: list[Mapping[str, object]] = []
    answers = iter(pages)

    async def _execute(self, provider_code, operation_code, inputs, *, actor, client=None):
        windows.append(dict(inputs))
        result = IntegrationExecutionResult(
            canonical_payload=list(next(answers)), metadata={}, status_code=200
        )
        # The seam hands back the call log's id too, so a step can point at the
        # exchange it came from.
        return result, None

    monkeypatch.setattr(IntegrationOperationService, "execute_operation", _execute)
    return windows


@pytest.mark.asyncio
async def test_raw_material_ledger_pages_until_a_short_page(test_engine, monkeypatch) -> None:
    """The window's own size is the only end-of-data signal this provider gives.

    A job that stopped at the first page would import one window of the set and
    report success; one that never stopped would loop on the last window.
    """
    windows = _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    written = await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    assert written == 3
    assert [(w["range_start"], w["range_end"]) for w in windows] == [(1, 2), (3, 4)]
    assert all("changed_date" not in w for w in windows)

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        rows = list((await session.execute(select(FoodItemReportRawMaterial))).scalars().all())
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_raw_material_ledger_sends_no_filter(test_engine, monkeypatch) -> None:
    """The window is the whole request — no 변경일자, ever.

    The operation does declare a `changed_from` (CHNG_DT) input, and this job
    sends it on no window: a bound would hide a record inserted later under an
    older timestamp, which the portal's own stamps make possible. The second run
    therefore re-reads and writes nothing, which is what proves the ledger
    compares instead of rewriting.
    """
    _script(monkeypatch, [[_record(1)]])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    assert await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10) == 1

    windows = _script(monkeypatch, [[_record(1)]])
    assert await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10) == 0
    assert list(windows[0]) == ["range_start", "range_end"]


@pytest.mark.asyncio
async def test_raw_material_ledger_stops_at_the_page_ceiling(test_engine, monkeypatch) -> None:
    """A provider that never shortens a page must not walk the table forever.

    Measured failure mode of this portal (on the sibling I2570 feed, same
    gateway): a filter it decides to ignore answers 200 with a full unfiltered
    page, which is indistinguishable from more data.
    """
    windows = _script(monkeypatch, [[_record(1)], [_record(2)], [_record(3)]])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    assert await sync_food_item_report_raw_material_ledger(page_size=1, max_pages=2) == 2
    assert len(windows) == 2


@pytest.mark.asyncio
async def test_raw_material_ledger_continues_the_interrupted_pass(test_engine, monkeypatch) -> None:
    """An initial load spans runs, and the second run must not start over.

    An initial load is many windows against a per-run page ceiling. A run that
    restarted at row 1 would re-read what it already has forever and the load
    would never reach the end.
    """
    _script(monkeypatch, [[_record(1)], [_record(2)]])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    assert await sync_food_item_report_raw_material_ledger(page_size=1, max_pages=2) == 2

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        checkpoint = await BatchCheckpointService(session).find_checkpoint(OPERATION_CODE)
    assert checkpoint is not None
    assert checkpoint.resume_position == 3

    windows = _script(monkeypatch, [[_record(3)], [_record(4)]])
    assert await sync_food_item_report_raw_material_ledger(page_size=1, max_pages=2) == 2
    assert [(w["range_start"], w["range_end"]) for w in windows] == [(3, 3), (4, 4)]


@pytest.mark.asyncio
async def test_raw_material_ledger_records_progress_after_every_page(
    test_engine, monkeypatch
) -> None:
    """The offset is stored per page, not per run.

    A run that saved only at the end would lose every window it had already
    imported when it is interrupted — and interruption is the case the
    checkpoint exists for.
    """
    windows = _script(monkeypatch, [[_record(1)], [_record(2)]])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    await sync_food_item_report_raw_material_ledger(page_size=1, max_pages=2)

    assert [(w["range_start"], w["range_end"]) for w in windows] == [(1, 1), (2, 2)]
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        checkpoint = await BatchCheckpointService(session).find_checkpoint(OPERATION_CODE)
    assert checkpoint is not None
    assert checkpoint.resume_position == 3


@pytest.mark.asyncio
async def test_raw_material_ledger_keeps_the_tail_and_verifies_it_next_run(
    test_engine, monkeypatch
) -> None:
    """A finished pass leaves the cursor one row past the last record read.

    That is what makes the next run incremental: it asks for the rows added
    since, not for the whole set again. The advance is by what the short page
    *held* (one record), not by the window's width — the two differ exactly at
    the tail, and using the width would leave a gap nobody would notice.

    The next run then starts one row *early*, re-reading the record the cursor
    was measured from. That overlap is the evidence the offset still means what
    it meant, and it rides in a page the run was fetching anyway.
    """
    _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        checkpoint = await BatchCheckpointService(session).find_checkpoint(OPERATION_CODE)
    assert checkpoint is not None
    assert (checkpoint.resume_position, checkpoint.resume_key) == (
        4,
        f"{ITEM_REPORT_NO}3",
    )

    # The feed is unchanged: the overlap row answers with the same key, and the
    # walk continues without re-reading the set.
    windows = _script(monkeypatch, [[_record(3)]])
    assert await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10) == 0
    assert windows[0]["range_start"] == 3

    async with factory() as session:
        checkpoint = await BatchCheckpointService(session).find_checkpoint(OPERATION_CODE)
    assert checkpoint is not None
    assert checkpoint.resume_position == 4


@pytest.mark.asyncio
async def test_raw_material_ledger_restarts_when_the_overlap_row_is_a_different_record(
    test_engine, monkeypatch
) -> None:
    """A moved feed sends the walk back to the first row.

    Rows were removed, so every later row shifted down and the offsets this
    walk recorded name different records now. Left alone the cursor would keep
    asking about positions that moved, and every later run would import the
    wrong rows or nothing at all — silently, because the provider answers 200
    either way. The record at the overlap offset is what says which happened.
    """
    _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    # The next run finds a different record where the anchor stood, looks one
    # window back for it, and only then starts over.
    windows = _script(
        monkeypatch, [[_record(9), _record(8)], [_record(1), _record(2)], [_record(7)]]
    )
    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    assert [w["range_start"] for w in windows] == [3, 1, 1]

    # The restarted walk read row 1 and stopped there (a short page), so the
    # cursor is the tail of what it actually read — not the offset it abandoned.
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        checkpoint = await BatchCheckpointService(session).find_checkpoint(OPERATION_CODE)
    assert checkpoint is not None
    assert (checkpoint.resume_position, checkpoint.resume_key) == (
        2,
        f"{ITEM_REPORT_NO}7",
    )


@pytest.mark.asyncio
async def test_raw_material_ledger_restarts_when_the_overlap_row_is_gone(
    test_engine, monkeypatch
) -> None:
    """An empty answer at the overlap offset is a feed shorter than the cursor.

    Before the overlap existed this was indistinguishable from "no new rows",
    and the walk would sit past an end that had moved — forever, without ever
    failing.
    """
    _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    windows = _script(monkeypatch, [[], [], [_record(1)]])
    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    assert [w["range_start"] for w in windows] == [3, 1, 1]

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        checkpoint = await BatchCheckpointService(session).find_checkpoint(OPERATION_CODE)
    assert checkpoint is not None
    assert checkpoint.resume_position == 2


async def _run_in_context(test_engine) -> object:
    """Open a run and put it in context, the way the scheduler does."""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        run = await BatchRunService(session).create_started_run(
            None, "sync_food_item_report_raw_material_ledger", "CRON", "scheduler"
        )
    current_run_id.set(run.id)
    return run.id


async def _steps(test_engine) -> list[BatchStep]:
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        return list(
            (await session.execute(select(BatchStep).order_by(BatchStep.sequence))).scalars().all()
        )


@pytest.mark.asyncio
async def test_each_page_is_recorded_as_a_step(test_engine, monkeypatch) -> None:
    """A run says the night worked; the steps say which windows it walked.

    Without them, "where did the load get to" is answerable only by counting
    ledger rows — which the feed's own duplicates make wrong.
    """
    _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])
    await _run_in_context(test_engine)

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    steps = await _steps(test_engine)
    assert [(s.sequence, s.range_start, s.range_end) for s in steps] == [(1, 1, 2), (2, 3, 4)]
    assert [(s.status, s.received, s.written) for s in steps] == [
        ("SUCCEEDED", 2, 2),
        ("SUCCEEDED", 1, 1),
    ]
    assert all(step.duration_ms >= 0 for step in steps)


@pytest.mark.asyncio
async def test_a_failing_window_is_recorded_before_the_job_dies(test_engine, monkeypatch) -> None:
    """The window that failed is the one worth naming.

    The run row only says the night failed; without the step, finding the
    window means replaying the pass.
    """
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

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    with pytest.raises(IntegrationError):
        await sync_food_item_report_raw_material_ledger(page_size=1, max_pages=3)

    steps = await _steps(test_engine)
    assert [(step.sequence, step.status) for step in steps] == [(1, "SUCCEEDED"), (2, "FAILED")]
    assert steps[1].error_code == "IntegrationError"
    assert steps[1].range_start == 2


@pytest.mark.asyncio
async def test_a_job_run_by_hand_records_no_steps(test_engine, monkeypatch) -> None:
    """A step without a run has nothing to belong to.

    A CLI run must still work — and inventing a run row for it would put an
    execution in the log that no schedule ever fired.
    """
    _script(monkeypatch, [[_record(1)]])
    current_run_id.set(None)

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    assert await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=1) == 1
    assert await _steps(test_engine) == []

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        assert (await session.execute(select(BatchRun))).scalars().all() == []


@pytest.mark.asyncio
async def test_raw_material_ledger_restarts_when_the_overlap_row_is_unreadable(
    test_engine, monkeypatch
) -> None:
    """A page whose records are not records cannot confirm the cursor.

    The comparison has two outcomes and only one of them is safe to guess: a
    key that cannot be read is treated as "not the anchor", so the walk
    re-reads from the first row and the ledger's upsert absorbs the repeat.
    Guessing the other way would advance past rows on the strength of a page
    nobody could parse.
    """
    _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    windows = _script(monkeypatch, [["not a record"], [], [_record(1)]])
    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    assert [w["range_start"] for w in windows] == [3, 1, 1]


@pytest.mark.asyncio
async def test_raw_material_ledger_reads_a_no_data_refusal_as_the_end(
    test_engine, monkeypatch
) -> None:
    """A feed whose contract rejects the no-data code ends the pass, not the run.

    The last page can be exactly as wide as its window, so the walk only learns
    the feed ended from the next window — and on an operation that does not list
    `INFO-200` among its accepted envelope values, that window arrives as a
    refusal. Raising there would fail the job every night from the moment the
    ledger caught up, which is the one night it should be cheapest.
    """
    _refusing_script(monkeypatch, [[_record(1), _record(2)]], "INFO-200")

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    # A full page, then the refusal: the pass ends without raising.
    assert await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10) == 2

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        checkpoint = await BatchCheckpointService(session).find_checkpoint(OPERATION_CODE)
    assert checkpoint is not None
    assert checkpoint.resume_position == 3


@pytest.mark.asyncio
async def test_raw_material_ledger_still_fails_on_a_refusal_that_is_not_the_end(
    test_engine, monkeypatch
) -> None:
    """Every other refusal is a failure, and the run says so.

    Reading one code as "the end" must not turn the provider's real complaints
    — a window too wide, a rejected key — into quiet successes.
    """
    _refusing_script(monkeypatch, [[_record(1), _record(2)]], "ERROR-336")

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    with pytest.raises(IntegrationError):
        await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)


@pytest.mark.asyncio
async def test_the_end_of_the_feed_is_not_logged_as_a_failed_step(test_engine, monkeypatch) -> None:
    """A run that ended exactly as designed holds no failed step.

    A step's status is derived from its error, so writing the end-of-feed step
    from the `except` block would stamp it FAILED while the run reported
    SUCCEEDED — a log that disagrees with itself, and the reader believes the
    row, not the summary.
    """
    await _run_in_context(test_engine)
    _refusing_script(monkeypatch, [[_record(1), _record(2)]], "INFO-200")

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    steps = await _steps(test_engine)
    assert [(step.sequence, step.status, step.received) for step in steps] == [
        (1, "SUCCEEDED", 2),
        (2, "SUCCEEDED", 0),
    ]
    assert [step.error_code for step in steps] == [None, None]


@pytest.mark.asyncio
async def test_the_verification_call_is_a_step_like_any_other(test_engine, monkeypatch) -> None:
    """The call that rejected the cursor is in the log, in sequence.

    It is the one event a reader comes to this table for — "why did the walk
    start over?" — and skipping it left a gap in the sequence that read as a
    lost page. The next step's window returning to row 1 is the answer.
    """
    _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    await _run_in_context(test_engine)
    _script(monkeypatch, [[_record(9), _record(8)], [_record(1), _record(2)], [_record(7)]])
    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    steps = await _steps(test_engine)
    assert [(step.sequence, step.range_start, step.written) for step in steps] == [
        (1, 3, 0),
        (2, 1, 0),
        (3, 1, 1),
    ]


@pytest.mark.asyncio
async def test_a_feed_that_ends_on_a_full_window_keeps_its_tail(test_engine, monkeypatch) -> None:
    """A full last window is followed by an empty one, and the cursor stays put.

    1,071,963 % 1000 = 963 today; on the night the set is an exact multiple, the
    walk learns the end only from the empty window after it. That window must
    advance nothing and keep the previous key - a cursor moved by the empty
    window's width would sit past the end, and one reset by it would re-read the
    set every night.
    """
    _script(monkeypatch, [[_record(1), _record(2)], []])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    assert await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10) == 2

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        checkpoint = await BatchCheckpointService(session).find_checkpoint(OPERATION_CODE)
    assert checkpoint is not None
    assert (checkpoint.resume_position, checkpoint.resume_key) == (3, f"{ITEM_REPORT_NO}2")


@pytest.mark.asyncio
async def test_the_hourly_quota_ends_the_run_and_keeps_the_cursor(test_engine, monkeypatch) -> None:
    """`INFO-320` is a quota, not the end of the feed and not a failure.

    Measured: 100 unfiltered calls per hour, against a feed of 194. Raised, the
    initial load would die at window 101 every hour and never finish; read as
    the end, the cursor would sit at the tail of a half-imported set. The run
    stops where it is, the checkpoint still names the refused window, and the
    next run opens it again.
    """
    _refusing_script(monkeypatch, [[_record(1)], [_record(2)]], "INFO-320")

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    assert await sync_food_item_report_raw_material_ledger(page_size=1, max_pages=5) == 2

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        checkpoint = await BatchCheckpointService(session).find_checkpoint(OPERATION_CODE)
    assert checkpoint is not None
    assert (checkpoint.resume_position, checkpoint.resume_key) == (3, f"{ITEM_REPORT_NO}2")

    # Next hour: the refused window answers, and the walk continues from it.
    windows = _script(monkeypatch, [[_record(2), _record(3)], [_record(4)]])
    assert await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=5) == 2
    assert [w["range_start"] for w in windows] == [2, 4]


@pytest.mark.asyncio
async def test_a_record_inserted_before_the_cursor_moves_the_walk_not_the_whole_feed(
    test_engine, monkeypatch
) -> None:
    """The anchor is still in the overlap window, a few rows down: continue from there.

    Measured on C002 (2026-09-06): three reports inserted somewhere in the
    first 191k rows moved the anchor from 190999 to 191002, and a restart at
    row 1 for that re-read 99 windows to write three rows. Against a
    1,072-window feed at 100 windows an hour, restarting on every small shift
    is an initial load that never finishes. Found in the window, the walk moves
    to the anchor's new position and verifies it there - no extra call.
    """
    _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    # One record now stands where the anchor stood; the anchor is one row down.
    windows = _script(
        monkeypatch, [[_record(9), _record(3)], [_record(3), _record(4)], [_record(5)]]
    )
    assert await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10) == 2
    assert [w["range_start"] for w in windows] == [3, 4, 6]


@pytest.mark.asyncio
async def test_a_record_removed_before_the_cursor_is_found_one_window_back(
    test_engine, monkeypatch
) -> None:
    """The anchor moved up, out of the overlap window: one probe behind finds it.

    A removal shifts every later row up, so the anchor sits before the window
    the cursor names. One window back costs one call; a restart costs the
    whole feed.
    """
    _script(monkeypatch, [[_record(1), _record(2)], [_record(3)]])

    from app.batch.sync_food_item_report_raw_material_ledger import (
        sync_food_item_report_raw_material_ledger,
    )

    await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10)

    # Record 2 was removed: the anchor (3) now sits at row 2, one before the window.
    windows = _script(
        monkeypatch,
        [
            [_record(4), _record(5)],
            [_record(1), _record(3)],
            [_record(3), _record(4)],
            [_record(5)],
        ],
    )
    assert await sync_food_item_report_raw_material_ledger(page_size=2, max_pages=10) == 2
    assert [w["range_start"] for w in windows] == [3, 1, 2, 4]
