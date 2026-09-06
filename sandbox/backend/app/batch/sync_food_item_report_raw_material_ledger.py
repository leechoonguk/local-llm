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
from app.schemas.batch.checkpoint import FIRST_POSITION
from app.services.batch.checkpoint import BatchCheckpointService
from app.services.batch.run import current_run_id
from app.services.batch.step import BatchStepService
from app.services.food.item_report_raw_material import FoodItemReportRawMaterialService
from app.services.integration.operation import IntegrationOperationService


# ============================================================
# Constants
# ============================================================

# The configuration this job runs, by the codes the seeds wrote (revisions 64,
# 106 and 107). The job names an operation, never a URL: the path, the key, the
# filters and the paging family all live in `integration_field`.
PROVIDER_CODE = "mfds-food-safety-korea"

OPERATION_CODE = "search-food-item-report-raw-material"

# C002 pages by row interval (the RANGE family), like every service of this
# portal: both bounds are required and have no default, so every call states its
# window — and the portal caps how wide it may be at 1000 rows
# (`ERROR-336 데이터요청은 한번에 최대 1000건을 넘을 수 없습니다`, measured on
# the sibling I2570 feed and documented by the portal for every service).
#
# The cap is the window: a narrower one costs the same fixed provider latency
# per call and buys nothing.
DEFAULT_PAGE_SIZE = 1000

# A ceiling, not a target: a pass stops on the first short page. It bounds a
# provider that never shortens one — a filter it decided to ignore answers 200
# with a full unfiltered page, the measured failure mode of this portal.
#
# **100 is the provider's documented hourly quota, not a size estimate.** The
# portal answers `INFO-320 CHNG_DT 파라미터를 사용하지 않으면 1시간당 100회까지만
# 호출할 수 있습니다` once an hour's unfiltered calls run out - measured to
# tolerate ~190 before refusing, which is not a number to plan on. The feed
# holds 1,071,963 records (`total_count`, 2026-09-06 - the same count as the
# I1250 registry it is the ingredients view of), so the initial load is ~1,072
# windows: **eleven nightly runs by construction** on one key, each walking 100
# and storing where it stopped; the provider's key pool multiplies what an
# hour buys without this job knowing (`backend-integration-configuration.md`). A ceiling above the
# quota would not read more; it would end the run on a refusal instead of on
# its own count.
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

# What this portal answers when the hour's unfiltered calls are spent - a
# quota, not an error and not the end of the feed. The run stops where it is
# and keeps its cursor; the next run continues. Raised instead, the initial load
# would fail every hour at window 101 and never finish; read as the end, it
# would leave the cursor at the tail of a set that is half imported.
QUOTA_CODES = frozenset({"INFO-320"})

# Written into `created_by`/`updated_by`: an audit trail states who wrote a row,
# and for these rows the answer is this job, not a person.
SYNCED_BY = "batch:sync_food_item_report_raw_material_ledger"


# ============================================================
# Functions
# ============================================================


async def sync_food_item_report_raw_material_ledger(
    page_size: int = DEFAULT_PAGE_SIZE, max_pages: int = DEFAULT_MAX_PAGES
) -> int:
    """Migrate the 식품(첨가물) 품목제조보고(원재료) (C002) records into the ingredients ledger.

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

    cursor = None if checkpoint is None else checkpoint.resume_position
    anchor = None if checkpoint is None else checkpoint.resume_key

    # A source with no cursor — never read, or a job that does not page by rows —
    # starts at the first one. The checkpoint says what it knows; what an unknown
    # means is this job's own decision.
    range_start = FIRST_POSITION if cursor is None else cursor

    # One row of overlap, so the first page carries the evidence that the cursor
    # still names the record it was written for. Skipped when the window is one
    # row wide: the overlap would fill it, the walk would re-read the anchor
    # forever and never advance.
    verifying = anchor is not None and range_start > FIRST_POSITION and page_size > 1
    if verifying:
        range_start -= 1

    written_count = 0
    run_id = current_run_id.get()
    # Steps number the calls made, not the loop's iterations: a re-anchor probe
    # is a call of its own, and two steps sharing a sequence is a UNIQUE error.
    calls_made = 0
    for _page in range(max_pages):
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
            calls_made += 1
            try:
                result, call_id = await integration_operation_service.execute_operation(
                    PROVIDER_CODE, OPERATION_CODE, window, actor=SYNCED_BY
                )
            except IntegrationError as exc:
                if await _refusal_ends_the_run(
                    exc, run_id, calls_made, window, started, integration_operation_service
                ):
                    break
                raise

        # The overlap row decides whether the offset still means what it meant.
        # Checked before the ledger write so a moved feed is not imported at the
        # wrong offsets first and reconciled afterwards.
        if verifying and anchor is not None:
            verifying = False
            if _row_key(result.canonical_payload, 0) != anchor:
                # The record the cursor was measured from is not where it was.
                # Before concluding the feed was re-ordered, look for it inside
                # this very window: a feed that gained a few records *before*
                # the cursor pushes the anchor a few rows down, and it is still
                # here. Measured on the sibling I1250 (2026-09-06): the anchor stood at
                # 190999 one day and 191002 the next - three reports inserted
                # somewhere in the first 191k - and restarting at row 1 for that
                # re-read 99 windows to write three rows. Against a 1,072-window
                # feed with 100 windows an hour, a restart on every small shift
                # is an initial load that never finishes.
                #
                # Found: continue from the anchor's new position - the next
                # iteration re-opens the window there and verifies it again,
                # so the resume is still proven, just one call later. Not
                # found: the anchor is behind this window (records removed) or
                # gone; look one window back once, then start over.
                #
                # The call still happened, so it is still a step - read, wrote
                # nothing. Skipping it left a hole in the run's sequence and hid
                # the one event a reader would come here for.
                await _record_step(
                    run_id,
                    calls_made,
                    window,
                    started,
                    received=len(result.canonical_payload),
                    written=0,
                    integration_call_id=call_id,
                )
                shift, calls_made = await _relocate_anchor(
                    result.canonical_payload, anchor, range_start, page_size, run_id, calls_made
                )
                if shift is None:
                    range_start = FIRST_POSITION
                    continue
                range_start += shift
                verifying = True
                continue

        # Write phase: one transaction per page, opened inside the service.
        async with AsyncSession(engine) as session:
            ledger_service = FoodItemReportRawMaterialService(session)
            received, written = await ledger_service.update_item_report_raw_material_ledger(
                result.canonical_payload, SYNCED_BY
            )

        await _record_step(
            run_id,
            calls_made,
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


async def _refusal_ends_the_run(
    exc: IntegrationError,
    run_id: UUID | None,
    step: int,
    window: dict[str, int],
    started: float,
    integration_operation_service: IntegrationOperationService,
) -> bool:
    """Record the refused window, and say whether the run simply ends there.

    Two refusals are answers, not failures, and both end the run where it is:
    - `INFO-200` past the last record - the window sits beyond the feed. A short
      page is the same fact when the operation's contract accepts the code; this
      branch is for the sibling feeds whose contract does not.
    - `INFO-320`, the hour's calls spent - nothing was read, nothing advances, the
      checkpoint already names this window and the next run opens it again.

    Either is recorded as the empty page it is: written from the `except` block
    with an error code, the step's status would be FAILED under a run that ended
    exactly as designed - a log disagreeing with itself. Any other refusal is a
    failure: recorded with its code, and the caller re-raises.

    Its own function so the walk stays under the statement cap - the three
    branches are one decision, "what does this code mean for the run".
    """
    ended = exc.envelope_value in END_OF_DATA_CODES or exc.envelope_value in QUOTA_CODES
    await _record_step(
        run_id,
        step,
        window,
        started,
        received=0 if ended else None,
        written=0 if ended else None,
        integration_call_id=integration_operation_service.last_call_id,
        error_code=None if ended else type(exc).__name__,
        error_detail=None if ended else exc.detail,
    )
    return ended


async def _relocate_anchor(
    payload: dict[str, object] | list[object],
    anchor: str,
    range_start: int,
    page_size: int,
    run_id: UUID | None,
    calls_made: int,
) -> tuple[int | None, int]:
    """How far the anchor moved, or None if it is nowhere near - plus the calls spent.

    First in the window just read (a forward shift: records inserted before the
    cursor push the anchor down, and it is still here at no extra cost); then in
    the one window behind it (a backward shift: records removed before the
    cursor pull it up), which is one more call and one more step. Beyond that
    the feed was re-ordered, and the caller starts over.
    """
    shift = _position_of(payload, anchor)
    if shift is not None or range_start <= FIRST_POSITION:
        return shift, calls_made
    behind_start = max(FIRST_POSITION, range_start - page_size)
    window = {"range_start": behind_start, "range_end": range_start - 1}
    started = perf_counter()
    async with AsyncSession(engine) as session:
        behind = IntegrationOperationService(session)
        calls_made += 1
        result, call_id = await behind.execute_operation(
            PROVIDER_CODE, OPERATION_CODE, window, actor=SYNCED_BY
        )
    await _record_step(
        run_id,
        calls_made,
        window,
        started,
        received=len(result.canonical_payload),
        written=0,
        integration_call_id=call_id,
    )
    found = _position_of(result.canonical_payload, anchor)
    return (None if found is None else found - (range_start - behind_start)), calls_made


def _position_of(payload: dict[str, object] | list[object], key: str) -> int | None:
    """Where one record sits in a page, by its natural key - or None.

    The re-anchor's question: "is the record the cursor was measured from still
    in this window, and how far did it move?"
    """
    records = payload if isinstance(payload, list) else [payload]
    for index, record in enumerate(records):
        if isinstance(record, dict) and _row_key([record], 0) == key:
            return index
    return None


def _row_key(payload: dict[str, object] | list[object], index: int) -> str | None:
    """The natural identity of one record of a page — `0` the first, `-1` the last.

    `item_report_no` is the ledger's own unique column, so the anchor and the
    row it protects are identified the same way: a key the ledger could not
    store is not a key this walk should resume from.

    A one-record page arrives as a bare object rather than a list, the same
    shape `update_item_report_raw_material_ledger` normalises, and an empty
    page answers None instead of raising — a page that carried nothing
    measured nothing.
    """
    records = payload if isinstance(payload, list) else [payload]
    if not records:
        return None
    record = records[index]
    if not isinstance(record, dict):
        return None
    code = record.get("item_report_no")
    return None if not isinstance(code, str) else code


async def _record_step(
    run_id: UUID | None,
    step: int,
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
            step,
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
    count = asyncio.run(sync_food_item_report_raw_material_ledger())
    print(f"Wrote {count} item report raw material ledger rows")
