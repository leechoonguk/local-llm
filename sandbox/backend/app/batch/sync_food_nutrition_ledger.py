# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio
from time import perf_counter
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.core.exceptions import IntegrationConfigurationError, IntegrationError
from app.schemas.batch.checkpoint import FIRST_POSITION
from app.services.batch.checkpoint import BatchCheckpointService
from app.services.batch.run import current_run_id
from app.services.batch.step import BatchStepService
from app.services.food.nutrition import FoodNutritionService
from app.services.integration.operation import IntegrationOperationService


# ============================================================
# Constants
# ============================================================

# The configuration this job runs, by the codes the seeds wrote. The publisher is
# 식품의약품안전처 either way; `data-go-kr` is the gateway it publishes I2790
# through, and the path, the key and the paging family live in
# `integration_field` rather than here.
PROVIDER_CODE = "data-go-kr"

OPERATION_CODE = "search-food-nutrition"

# I2790 pages by page number (the PAGE family), not by row interval like the
# `mfds-food-safety-korea` ledgers: `pageNo` + `numOfRows`, both required.
#
# **500 is the provider's ceiling, and exceeding it is silent.** Measured
# (2026-09-05): `numOfRows` of 501, 510, 550, 590, 600, 700, 750, 800, 900, 999
# and 1000 all answer HTTP 200 with an empty item list - the same shape as the
# end of the feed. A job asking for 1000 rows would import nothing, stop on the
# "short" first page and report success every night.
DEFAULT_PAGE_SIZE = 500

MAX_PAGE_SIZE = 500

# A ceiling, not a target: a pass stops on the first short page. Measured
# (2026-09-05): the feed ends at 319,060 records, so a full pass is 639 calls at
# the maximum window. 800 leaves room for the set to grow by a quarter before a
# pass would stop short of the end, and still bounds a provider that never
# shortens a page.
DEFAULT_MAX_PAGES = 800

# Written into `created_by`/`updated_by`: an audit trail states who wrote a row,
# and for these rows the answer is this job, not a person.
SYNCED_BY = "batch:sync_food_nutrition_ledger"


# ============================================================
# Functions
# ============================================================


async def sync_food_nutrition_ledger(
    page_size: int = DEFAULT_PAGE_SIZE, max_pages: int = DEFAULT_MAX_PAGES
) -> int:
    """Migrate the 식품 영양성분 (I2790) records into the nutrition ledger.

    **A pass, not a run.** One pass walks the provider's whole set; a run walks
    at most `max_pages` of it and stores which page it stopped on. So the
    319k-record load survives being interrupted - by the ceiling, by an outage,
    by a deploy - and continues from the next page instead of starting over.

    **The cursor is the last page imported, not the next one.** A page walk's
    new records land at the end of the last page, so a run resumes *on* the page
    it finished rather than past it: the next run re-reads that page, picks up
    whatever was appended, and a caught-up night costs one call. A cursor one
    page further would step over every record added since.

    **The end of the feed has one shape here, and it is also the shape of a
    window this provider refuses.** There is no envelope code for "no rows":
    HTTP 200 with an empty list is both "you have reached the end" and "your
    `numOfRows` was too large" (measured: 501 rows and up answer empty). The job
    cannot tell them apart at the call site, so it refuses the ambiguity before
    making the call - see `MAX_PAGE_SIZE`.

    **The overlap is a page, and the anchor is that page's *first* record.** A
    page walk cannot re-read one record - positions move a page at a time - so
    the re-read page is the whole overlap, and it is the page the run was going
    to fetch anyway:

    | The resumed page | Means | The walk |
    |---|---|---|
    | same first key | the feed has not shifted under the cursor | continues |
    | different first key | records were removed or re-ordered | restarts at page 1 |
    | empty | the feed is now shorter than the cursor | restarts at page 1 |

    The *first* record, not the last: appending to the resumed page is the normal
    case here, and it changes that page's last record every time new food is
    published. Anchored on the last key, every ordinary night would read as a
    shifted feed and re-import the whole 319k set.

    It costs no extra write either: the ledger's upsert compares before it
    writes, so a re-read page is matched and left alone.

    What it does not catch, stated plainly: a page walk sees records appended
    past the cursor, never an edit to a record behind it. The portal stamps rows
    with `UPDATE_DATE`, which this ledger stores, so a later job could follow
    that as a change feed - this one does not, and a full re-read is what
    refreshes an edited row today.

    Returns the number of ledger rows written (inserted or refreshed).
    """
    if page_size > MAX_PAGE_SIZE:
        # Refused rather than clamped: a caller asking for 900 believes it will
        # get 900, and this provider answers that belief with an empty page that
        # reads as the end of the feed. Silently narrowing the window would keep
        # the wrong belief alive in the caller.
        raise IntegrationConfigurationError(
            f"page_size {page_size} exceeds the {MAX_PAGE_SIZE}-row ceiling of "
            f"{OPERATION_CODE}; larger windows answer HTTP 200 with no rows"
        )

    # Read phase: a fresh session's close() releases the autobegun read
    # transaction. No session.begin() here - transactions belong to services.
    async with AsyncSession(engine) as session:
        batch_checkpoint_service = BatchCheckpointService(session)
        checkpoint = await batch_checkpoint_service.find_checkpoint(OPERATION_CODE)

    cursor = None if checkpoint is None else checkpoint.resume_position
    anchor = None if checkpoint is None else checkpoint.resume_key

    # A source with no cursor - never read, or a job that pages differently -
    # starts at the first page. The checkpoint says what it knows; what an
    # unknown means is this job's own decision.
    page_no = FIRST_POSITION if cursor is None else cursor

    # The resumed page carries its own evidence: its first record is what the
    # anchor was measured from. A run that has never stored one has nothing to
    # compare and simply reads.
    verifying = anchor is not None

    written_count = 0
    # The last page this run imported, as (page, first key): an empty page has
    # two meanings, and which one applies depends on whether a page before it
    # was filled by this very run.
    imported: tuple[int, str | None] | None = None
    run_id = current_run_id.get()
    for step in range(max_pages):
        # Paging keys and nothing else: the format selector is a seeded literal,
        # and a filter would turn the migration into a subset.
        window: dict[str, int] = {"page_no": page_no, "num_of_rows": page_size}
        # The step log speaks in rows, like its siblings, so a reader comparing
        # two ledgers' runs is comparing the same unit.
        rows = {
            "range_start": (page_no - 1) * page_size + 1,
            "range_end": page_no * page_size,
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
                # The window that failed is the one worth naming: the run's own
                # row only says the night failed. The call id comes off the
                # service because the raise carried no return value.
                await _record_step(
                    run_id,
                    step,
                    rows,
                    started,
                    integration_call_id=integration_operation_service.last_call_id,
                    error_code=type(exc).__name__,
                    error_detail=exc.detail,
                )
                raise

        records = _records(result.canonical_payload)

        # The overlap page decides whether the cursor still means what it meant.
        # Checked before the ledger write so a shifted feed is not imported at
        # the wrong pages first and reconciled afterwards.
        if verifying:
            verifying = False
            if _row_key(records, 0) != anchor:
                # The record the cursor was measured from is gone or displaced:
                # every page after it holds different records now. Start over,
                # and let this run's remaining pages do the first ones.
                #
                # The call still happened, so it is still a step - read, wrote
                # nothing. The next step's window returning to page 1 is what
                # says why.
                await _record_step(
                    run_id,
                    step,
                    rows,
                    started,
                    received=len(records),
                    written=0,
                    integration_call_id=call_id,
                )
                page_no = FIRST_POSITION
                anchor = None
                continue

        # Write phase: one transaction per page, opened inside the service.
        async with AsyncSession(engine) as session:
            food_nutrition_service = FoodNutritionService(session)
            received, written = await food_nutrition_service.update_nutrition_ledger(
                result.canonical_payload, SYNCED_BY
            )

        await _record_step(
            run_id,
            step,
            rows,
            started,
            received=received,
            written=written,
            integration_call_id=call_id,
        )
        written_count += written

        # A page shorter than the window is the last one - this provider gives no
        # "has more" flag, and its `totalCount` is not read for the same reason
        # the sibling ledgers do not read theirs: the walk's own answer is
        # cheaper and cannot disagree with itself.
        completed = received < page_size

        if received > 0:
            # The page just imported is where the next run resumes, and its first
            # record is what will prove the position still holds.
            imported = (page_no, _row_key(records, 0))
            resume_page, anchor = imported
        elif imported is not None:
            # Empty right after a page this run filled: the feed ended on a full
            # page, and this is the page past it. Resume on the full one - the
            # next record will be appended there. Read as a shifted feed instead,
            # this sent the cursor back to page 1 and the next night re-walked
            # all 639 pages to write nothing (planted: 4 records, 2 per page).
            resume_page, anchor = imported
        else:
            # Empty at the position the run started from, with nothing imported
            # to fall back on: the feed is shorter than the cursor. Restart rather
            # than sit past an end that moved - a cursor beyond the feed would
            # answer empty forever.
            resume_page, anchor = FIRST_POSITION, None

        # Stored after the ledger write, never before: a crash between the two
        # re-reads one page, and the upsert absorbs it. The reverse order would
        # skip records nobody would notice were missing.
        async with AsyncSession(engine) as session:
            batch_checkpoint_service = BatchCheckpointService(session)
            await batch_checkpoint_service.update_resume_point(
                OPERATION_CODE, resume_page, anchor, SYNCED_BY
            )

        if completed:
            break

        page_no += 1

    return written_count


def _records(payload: dict[str, object] | list[object]) -> list[object]:
    """One page as a list, whatever shape it arrived in.

    A one-record page arrives as a bare object rather than a list - the same
    shape `FoodNutritionService.update_nutrition_ledger` normalises.
    """
    return payload if isinstance(payload, list) else [payload]


def _row_key(records: list[object], index: int) -> str | None:
    """The natural identity of one record of a page - `0` the first, `-1` the last.

    `food_code` is the ledger's own unique column, so the anchor and the page it
    protects are identified the same way: a key the ledger could not store is not
    a key this walk should resume from. Measured over the whole feed: 319,060
    records, 319,060 distinct codes, no duplicate.

    An empty page answers None instead of raising - a page that carried nothing
    measured nothing.
    """
    if not records:
        return None
    record = records[index]
    if not isinstance(record, dict):
        return None
    code = record.get("food_code")
    return None if not isinstance(code, str) else code


async def _record_step(
    run_id: UUID | None,
    step: int,
    rows: dict[str, int],
    started: float,
    *,
    received: int | None = None,
    written: int | None = None,
    integration_call_id: UUID | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    """Record one page, if this job is running under a scheduled run.

    A job started by hand has no run in context and writes no step: a step
    without a run has nothing to belong to, and inventing one would put a run in
    the log that no schedule ever fired.
    """
    if run_id is None:
        return
    async with AsyncSession(engine) as session:
        batch_step_service = BatchStepService(session)
        await batch_step_service.create_finished_step(
            run_id,
            step + 1,
            round((perf_counter() - started) * 1000),
            SYNCED_BY,
            range_start=rows["range_start"],
            range_end=rows["range_end"],
            received=received,
            written=written,
            integration_call_id=integration_call_id,
            error_code=error_code,
            error_detail=error_detail,
        )


if __name__ == "__main__":  # pragma: no cover — entry point, not testable logic
    count = asyncio.run(sync_food_nutrition_ledger())
    print(f"Wrote {count} nutrition ledger rows")
