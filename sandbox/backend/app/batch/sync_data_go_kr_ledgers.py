# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from itertools import count
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.core.exceptions import IntegrationError, LedgerFloorError
from app.core.integration import IntegrationPage, window_rows
from app.core.ledger import Feed
from app.services.batch.run import current_run_id
from app.services.batch.step import BatchStepService
from app.services.food.nutrition import FoodNutritionService
from app.services.integration.operation import IntegrationOperationService


# ============================================================
# Constants
# ============================================================

logger = structlog.get_logger(__name__)

# The provider this job reads, by the code the seeds wrote (revision 74). The
# data behind it is 식품의약품안전처 either way; `data-go-kr` is the gateway it
# publishes I2790 through, and the path, the key and the paging family live in
# `integration_field` rather than here.
PROVIDER_CODE = "data-go-kr"

# I2790 pages by page number (the PAGE family) and **500 is the gateway's
# ceiling, exceeded silently**: measured (2026-09-05), `numOfRows` of 501 up
# to 1000 all answer HTTP 200 with an empty item list — the same shape as the
# end of the feed. A wider window would read nothing, stop on the "short"
# first page, and the floor would refuse the empty pass every night.
PAGE_SIZE = 500

# The gateway has no envelope code for "no rows": a window past the last
# record is an empty page, which is the walk's own end rule.
END_CODES: frozenset[str] = frozenset()

# Written into `created_by`/`updated_by`: an audit trail states who wrote a
# row, and for these rows the answer is this job, not a person.
SYNCED_BY = "batch:sync_data_go_kr_ledgers"


# One feed today. The tuple is the same shape as the sibling provider job's so
# a second data.go.kr operation is one row here, not a second job.
FEEDS: tuple[Feed, ...] = (
    Feed(
        "search-food-nutrition", FoodNutritionService, FoodNutritionService.replace_nutrition_ledger
    ),
)


# ============================================================
# Functions
# ============================================================


async def sync_data_go_kr_ledgers() -> int:
    """Replace every data.go.kr ledger with a whole pass of its feed.

    The same rule as the 식품안전나라 job, stated for this gateway's dialect:
    read pages of `PAGE_SIZE` rows from the first until one comes back short,
    then make the ledger equal what was read. No cursor is kept and no
    `total_count` is consulted; a run reads the whole feed every night.
    Measured (2026-09-05), I2790 ends at 319,060 records — 639 windows at
    the ceiling, on a quota this gateway has not refused.

    **Feeds fail alone.** A feed whose pass could not finish — the provider
    refused, or the pass came back under the floor — leaves its ledger as it
    was and the job goes on to the next; the first failure is raised once
    every feed had its turn, so the run reads FAILED and the other ledgers
    are still tonight's.

    Returns the number of ledger rows the night changed, over every feed.
    """
    run_id = current_run_id.get()
    # Steps number the calls the run made, across feeds: two steps sharing a
    # sequence is a UNIQUE error, and a reader follows `integration_call_id`
    # to learn which feed a step belongs to.
    sequence = count(1)
    written = 0
    failures: list[Exception] = []
    # The ledger session is pinned to one connection because the stage a pass
    # fills is a TEMP table, and a TEMP table lives on the connection that
    # created it. The calls get a session of their own: their configuration
    # reads and call logs must not share a transaction with the stage.
    async with (
        engine.connect() as connection,
        AsyncSession(connection) as ledger_session,
        AsyncSession(engine) as call_session,
    ):
        integration_operation_service = IntegrationOperationService(call_session)
        for feed in FEEDS:
            pages = integration_operation_service.walk_operation(
                PROVIDER_CODE,
                feed.operation_code,
                actor=SYNCED_BY,
                page_size=PAGE_SIZE,
                end_codes=END_CODES,
            )
            recorded = _record_pages(pages, run_id, sequence, integration_operation_service)
            try:
                _, changed = await feed.replace(feed.service(ledger_session), recorded, SYNCED_BY)
            except (IntegrationError, LedgerFloorError) as exc:
                logger.warning(
                    "batch.ledger.feed_failed",
                    provider=PROVIDER_CODE,
                    operation=feed.operation_code,
                    error=str(exc),
                )
                failures.append(exc)
                continue
            written += changed
    if failures:
        raise failures[0]
    return written


async def _record_pages(
    pages: AsyncIterator[IntegrationPage],
    run_id: UUID | None,
    sequence: Iterator[int],
    integration_operation_service: IntegrationOperationService,
) -> AsyncIterator[list[object]]:
    """Hand each page on to the ledger, writing one step per window as it passes.

    Either ending writes a step: the run's own row only says the night
    failed, and the window is the fact a reader needs. A refusal arrives
    before the walk could say which window it was asking for, so the step
    names the one after the last page — which is the window the walk asks
    for after a full page, always — and points at the call log row through
    the service, since the raise carried no return value.
    """
    last_row = 0
    try:
        async for page in pages:
            last_row = window_rows(page.window)[1]
            await _record_step(
                run_id,
                next(sequence),
                window_rows(page.window),
                page.duration_ms,
                received=len(page.records),
                integration_call_id=page.call_id,
            )
            yield page.records
    except IntegrationError as exc:
        await _record_step(
            run_id,
            next(sequence),
            (last_row + 1, last_row + PAGE_SIZE),
            0,
            integration_call_id=integration_operation_service.last_call_id,
            error_code=type(exc).__name__,
            error_detail=exc.detail,
        )
        raise


async def _record_step(
    run_id: UUID | None,
    step: int,
    rows: tuple[int, int],
    duration_ms: int,
    *,
    received: int | None = None,
    integration_call_id: UUID | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    """Record one window, if this job is running under a scheduled run.

    A job started by hand has no run in context and writes no step: a step
    without a run has nothing to belong to, and inventing one would put a run
    in the log that no schedule ever fired. `written` is left empty on
    purpose: a stage merge changes rows per feed, not per window.
    """
    if run_id is None:
        return
    async with AsyncSession(engine) as session:
        batch_step_service = BatchStepService(session)
        await batch_step_service.create_finished_step(
            run_id,
            step,
            duration_ms,
            SYNCED_BY,
            range_start=rows[0],
            range_end=rows[1],
            received=received,
            integration_call_id=integration_call_id,
            error_code=error_code,
            error_detail=error_detail,
        )


if __name__ == "__main__":  # pragma: no cover — entry point, not testable logic
    total = asyncio.run(sync_data_go_kr_ledgers())
    print(f"Changed {total} ledger rows")
