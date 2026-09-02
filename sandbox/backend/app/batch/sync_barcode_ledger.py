# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio
from time import perf_counter
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.core.exceptions import IntegrationError
from app.schemas.batch.checkpoint import FIRST_RANGE_START
from app.services.barcode import BarcodeService
from app.services.batch.checkpoint import BatchCheckpointService
from app.services.batch.run import current_run_id
from app.services.batch.step import BatchStepService
from app.services.integration.operation import IntegrationOperationService


# ============================================================
# Constants
# ============================================================

# The configuration this job runs, by the codes the seeds wrote (revisions 64
# and 72). The job names an operation, never a URL: the path, the key, the
# filters and the paging family all live in `integration_field`.
PROVIDER_CODE = "mfds-food-safety-korea"

OPERATION_CODE = "search-barcode-item-info"

# I2570 pages by row interval (the RANGE family): both bounds are required and
# have no default, so every call states its window — and the provider caps how
# wide that window may be.
#
# Measured (2026-09-02): 1..1000 and 1001..2000 answer INFO-000 with 1000 rows;
# 1..1002 answers `ERROR-336 데이터요청은 한번에 최대 1000건을 넘을 수 없습니다`.
# 1..1001 is *accepted* — their validator compares `end - start` against 1000
# rather than the row count — and that extra row is not taken: it rides a
# provider bug, so the day it is fixed every page of this job becomes a 502.
#
# The full window costs 1.9s and 275KB, well inside the operation's
# `read_timeout_ms` of 15000, and latency is dominated by the provider's fixed
# cost rather than the row count (a 5-row call measured 2.3-7.0s). A full pass
# is therefore 54 calls instead of 533.
DEFAULT_PAGE_SIZE = 1000

# A ceiling, not a target: a pass stops on the first short page. It bounds a
# provider that never shortens one — a filter it decided to ignore answers 200
# with a full unfiltered page, the measured failure mode of this portal.
#
# It must still exceed the whole set, because the cursor only advances once a
# pass reaches the end: 100 x 1000 = 100,000 against a measured total_count of
# 53,242 (72_seed_barcode_item_info_integration_operation).
DEFAULT_MAX_PAGES = 100

# What this portal answers when a window holds no rows: `INFO-200 해당하는
# 데이터가 없습니다`, measured on a window past the last record (HTTP 200,
# empty payload). Whether it arrives as an empty page or as a refusal is the
# operation's own contract: `search-barcode-item-info` lists the code among its
# accepted envelope values, so the walk sees an empty page — a sibling feed that
# does not list it raises instead, and the end of the ledger would read as a
# failure every night once the walk caught up. Both are the same fact, so the
# job names it once here.
END_OF_DATA_CODES = frozenset({"INFO-200"})

# Written into `created_by`/`updated_by`: an audit trail states who wrote a row,
# and for these rows the answer is this job, not a person.
SYNCED_BY = "batch:sync_barcode_ledger"


# ============================================================
# Functions
# ============================================================


async def sync_barcode_ledger(
    page_size: int = DEFAULT_PAGE_SIZE, max_pages: int = DEFAULT_MAX_PAGES
) -> int:
    """Migrate the 식품바코드 품목정보 (I2570) records into the barcode ledger.

    **A pass, not a run.** One pass walks the provider's whole set; a run walks
    at most `max_pages` of it and stores where it stopped. So the 53k-row load
    survives being interrupted — by the ceiling, by an outage, by a deploy —
    and continues from the next window instead of starting over. This is only
    sound because the provider's row order is stable: measured on I2570, the
    same window answers the same rows minutes apart, with no overlap or gap at
    the page boundary.

    **The cursor stays at the tail.** A finished pass leaves the checkpoint one
    row past the last record read, so the next run asks for the increment and
    nothing else — a caught-up night costs one call instead of the 54 a restart
    costs. Resetting to row 1 was the earlier behaviour and it re-read 53k rows
    every night to write nothing.

    **The end of the feed has two shapes, and `total_count` is neither.** The
    count is not usable for the job — some operations on this portal report a
    fixed `1` whatever the set holds — so the end comes from the rows:

    | Shape | When |
    |---|---|
    | fewer records than the window asked for | the window straddles the last record |
    | `INFO-200 해당하는 데이터가 없습니다` | the window sits entirely past it |

    Both are needed because a page can be exactly as wide as its window: when
    the last record lands on the boundary, the walk only learns the feed ended
    from the *next* window, which holds nothing. Whether that arrives as an
    empty page or as a refusal is the operation's contract — this one lists the
    code among its accepted envelope values, a sibling feed may not — so the job
    treats the code as the end either way (`END_OF_DATA_CODES`).

    **The offset is verified, not assumed.** An offset names a position in a
    feed that can be re-ordered under it: delete one record and every later row
    shifts down, so a stored `53243` points at a different record than the one
    it was written for. So a run that has a cursor re-reads **one row it already
    consumed** — the first window starts at `cursor - 1` — and compares that
    record's natural key with the key stored beside the offset:

    | The overlap row | Means | The walk |
    |---|---|---|
    | same key | the feed has not moved under the cursor | continues from the cursor |
    | different key | rows were removed or re-ordered | restarts at row 1 |
    | missing (empty page) | the feed is now shorter than the cursor | restarts at row 1 |

    That costs no extra call — the row rides in the page the run was going to
    fetch anyway — and no extra write: the ledger's upsert compares before it
    writes, so a re-read record is matched and left alone.

    What it does not catch, stated plainly: an offset walk sees rows *appended*
    past the cursor, never an edit to a record behind it. This job accepts that,
    because the provider stamps every row `LAST_UPDT_DTM = 2015-01-22` (4000
    sampled across 1..2000, 26000..26999, 52243..53242) — there is no change feed
    to follow and no timestamp that would tell an edited row from an untouched
    one.

    **No 변경일자 filter is sent.** A bound that narrowed would hide a row
    inserted later under an older timestamp; the walk has no such blind spot.

    Returns the number of ledger rows written (inserted or refreshed).
    """
    # Read phase: a fresh session's close() releases the autobegun read
    # transaction. No session.begin() here — transactions belong to services.
    async with AsyncSession(engine) as session:
        batch_checkpoint_service = BatchCheckpointService(session)
        checkpoint = await batch_checkpoint_service.find_checkpoint(OPERATION_CODE)

    cursor = None if checkpoint is None else checkpoint.next_range_start
    anchor = None if checkpoint is None else checkpoint.last_row_key

    # A source with no cursor — never read, or a job that does not page by rows —
    # starts at the first one. The checkpoint says what it knows; what an unknown
    # means is this job's own decision.
    range_start = FIRST_RANGE_START if cursor is None else cursor

    # One row of overlap, so the first page carries the evidence that the cursor
    # still names the record it was written for. Skipped when the window is one
    # row wide: the overlap would fill it, the walk would re-read the anchor
    # forever and never advance.
    verifying = anchor is not None and range_start > FIRST_RANGE_START and page_size > 1
    if verifying:
        range_start -= 1

    written_count = 0
    run_id = current_run_id.get()
    for page in range(max_pages):
        window: dict[str, int] = {
            "range_start": range_start,
            "range_end": range_start + page_size - 1,
        }
        started = perf_counter()

        # The external call gets its own session: it resolves the operation
        # configuration by reading, and holding that read open across the page's
        # write transaction would be one idle transaction per window.
        async with AsyncSession(engine) as session:
            integration_operation_service = IntegrationOperationService(session)
            try:
                result, call_id = await integration_operation_service.execute_operation(
                    PROVIDER_CODE, OPERATION_CODE, window, actor=SYNCED_BY
                )
            except IntegrationError as exc:
                # Either ending writes a step before the job returns or dies:
                # the run's own row only says the night failed, and the window is
                # the fact a reader needs. The call id comes off the service
                # because the raise carried no return value — it is what lets a
                # reader go from this step to the provider's own answer.
                if exc.envelope_value in END_OF_DATA_CODES:
                    # The provider said "no rows here", which is an answer, not a
                    # failure: the window sits past the last record. A short page
                    # is the same fact when the operation's contract accepts that
                    # code as a valid envelope — this branch is for the sibling
                    # feeds whose contract does not, where the end of the walk
                    # arrives as a refusal and would otherwise fail every night
                    # from the moment the ledger caught up.
                    #
                    # Recorded as the empty page it is. Writing the step from the
                    # `except` block instead would carry `error_code`, and the
                    # step's status is derived from that — so a run that ended
                    # exactly as designed would hold a FAILED step and still
                    # report SUCCEEDED, a log disagreeing with itself.
                    await _record_step(
                        run_id,
                        page,
                        window,
                        started,
                        received=0,
                        written=0,
                        integration_call_id=integration_operation_service.last_call_id,
                    )
                    break

                await _record_step(
                    run_id,
                    page,
                    window,
                    started,
                    integration_call_id=integration_operation_service.last_call_id,
                    error_code=type(exc).__name__,
                    error_detail=exc.detail,
                )
                raise

        # The overlap row decides whether the offset still means what it meant.
        # Checked before the ledger write so a moved feed is not imported at the
        # wrong offsets first and reconciled afterwards.
        if verifying:
            verifying = False
            if _row_key(result.canonical_payload, 0) != anchor:
                # The record the cursor was measured from is gone or displaced:
                # every offset after it names a different row now. Start over,
                # and let this run's remaining pages do the first windows.
                #
                # The call still happened, so it is still a step — read, wrote
                # nothing. Skipping it left a hole in the run's sequence and hid
                # the one event a reader would come here for; the next step's
                # window returning to row 1 is what says why.
                await _record_step(
                    run_id,
                    page,
                    window,
                    started,
                    received=len(result.canonical_payload),
                    written=0,
                    integration_call_id=call_id,
                )
                range_start = FIRST_RANGE_START
                continue

        # Write phase: one transaction per page, opened inside the service.
        async with AsyncSession(engine) as session:
            barcode_service = BarcodeService(session)
            received, written = await barcode_service.update_barcode_ledger(
                result.canonical_payload, SYNCED_BY
            )

        await _record_step(
            run_id,
            page,
            window,
            started,
            received=received,
            written=written,
            integration_call_id=call_id,
        )

        written_count += written

        # A page shorter than the window is the last one — this provider has no
        # cursor and no "has more" flag, so the window's own size is the signal.
        # An empty page is the same fact at its limit: nothing left to read.
        completed = received < page_size

        # Advance by what the page actually held, not by the window's width: on a
        # short page those differ, and the difference is exactly the tail. Landing
        # one row past the last record read is what lets the next run ask for the
        # increment instead of re-reading the set.
        range_start += received if completed else page_size

        # The key travels with the offset it was measured from: it is the last
        # record of this page, the one sitting at `range_start - 1`. An empty
        # page measured nothing, so the previous key stands.
        anchor = _row_key(result.canonical_payload, -1) or anchor

        # Stored after the ledger write, never before: a crash between the two
        # re-reads one window, and the upsert absorbs it. The reverse order
        # would skip rows nobody would notice were missing.
        async with AsyncSession(engine) as session:
            batch_checkpoint_service = BatchCheckpointService(session)
            await batch_checkpoint_service.update_resume_point(
                OPERATION_CODE, range_start, anchor, SYNCED_BY
            )

        if completed:
            break

    return written_count


def _row_key(payload: dict[str, object] | list[object], index: int) -> str | None:
    """The natural identity of one record of a page — `0` the first, `-1` the last.

    `(barcode_no, report_no)` is the ledger's own unique key
    (`uq_barcode_barcode_no_report_no`), so the anchor and the row it protects
    are identified the same way: a key the ledger could not store is not a key
    this walk should resume from.

    A one-record page arrives as a bare object rather than a list, the same
    shape `BarcodeService.update_barcode_ledger` normalises, and an empty page
    answers None instead of raising — a page that carried nothing measured
    nothing.
    """
    records = payload if isinstance(payload, list) else [payload]
    if not records:
        return None
    record = records[index]
    if not isinstance(record, dict):
        return None
    return f"{record.get('barcode_no', '')}:{record.get('report_no', '')}"


async def _record_step(
    run_id: UUID | None,
    page: int,
    window: dict[str, int],
    started: float,
    *,
    received: int | None = None,
    written: int | None = None,
    integration_call_id: UUID | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    """Record one window, if this job is running under a scheduled run.

    A job started by hand has no run in context and writes no step: a step
    without a run has nothing to belong to, and inventing one would put a run
    in the log that no schedule ever fired.
    """
    if run_id is None:
        return
    async with AsyncSession(engine) as session:
        batch_step_service = BatchStepService(session)
        await batch_step_service.create_finished_step(
            run_id,
            page + 1,
            round((perf_counter() - started) * 1000),
            SYNCED_BY,
            range_start=window["range_start"],
            range_end=window["range_end"],
            received=received,
            written=written,
            integration_call_id=integration_call_id,
            error_code=error_code,
            error_detail=error_detail,
        )


if __name__ == "__main__":  # pragma: no cover — entry point, not testable logic
    count = asyncio.run(sync_barcode_ledger())
    print(f"Wrote {count} barcode ledger rows")
