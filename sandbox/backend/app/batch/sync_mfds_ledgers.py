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
from app.services.food.barcode import FoodBarcodeService
from app.services.food.item_report import FoodItemReportService
from app.services.food.item_report_raw_material import FoodItemReportRawMaterialService
from app.services.food.product_classification import FoodProductClassificationService
from app.services.food.raw_material import FoodRawMaterialService
from app.services.food.test_item import FoodTestItemService
from app.services.integration.operation import IntegrationOperationService


# ============================================================
# Constants
# ============================================================

logger = structlog.get_logger(__name__)

# The provider this job reads, by the code the seeds wrote (revision 64). A
# job names operations, never URLs: the path, the key, the filters and the
# paging family all live in `integration_field`.
PROVIDER_CODE = "mfds-food-safety-korea"

# Every service of this portal pages by row interval and caps the window at
# 1000 rows (`ERROR-336 데이터요청은 한번에 최대 1000건을 넘을 수 없습니다`,
# measured on I2570 and documented for every service). The cap is the window:
# a narrower one costs the same provider latency per call and buys nothing.
PAGE_SIZE = 1000

# What this portal answers when a window holds no rows: `INFO-200 해당하는
# 데이터가 없습니다`, measured on a window past the last record. Some
# operations list it among their accepted envelope values and the walk sees an
# empty page; the rest refuse with it. Both are the end of the feed, and the
# walk reads the refusal as the empty page it means.
END_CODES = frozenset({"INFO-200"})

# Written into `created_by`/`updated_by`: an audit trail states who wrote a
# row, and for these rows the answer is this job, not a person.
SYNCED_BY = "batch:sync_mfds_ledgers"


# Walked in this order, one after the other: the feeds share one key pool and
# one hourly quota, so two walking at once would only take turns being refused.
# Smallest first, so a night that runs out of quota still finished something
# (whole feeds, 2026-09-06: 3,393 / 9,633 / 43,609 / 51,161 / 1,071,961 /
# 1,071,961 rows).
FEEDS: tuple[Feed, ...] = (
    Feed("search-test-item", FoodTestItemService, FoodTestItemService.replace_test_item_ledger),
    Feed(
        "search-product-classification",
        FoodProductClassificationService,
        FoodProductClassificationService.replace_product_classification_ledger,
    ),
    Feed(
        "search-food-raw-material",
        FoodRawMaterialService,
        FoodRawMaterialService.replace_raw_material_ledger,
    ),
    Feed("search-barcode-item-info", FoodBarcodeService, FoodBarcodeService.replace_barcode_ledger),
    Feed(
        "search-food-item-report",
        FoodItemReportService,
        FoodItemReportService.replace_item_report_ledger,
    ),
    Feed(
        "search-food-item-report-raw-material",
        FoodItemReportRawMaterialService,
        FoodItemReportRawMaterialService.replace_item_report_raw_material_ledger,
    ),
)


# ============================================================
# Functions
# ============================================================


async def sync_mfds_ledgers() -> int:
    """Replace every 식품안전나라 ledger with a whole pass of its feed.

    One rule for every feed, whatever the operation: read windows of
    `PAGE_SIZE` rows from the first until one comes back short, then make the
    ledger equal what was read. No cursor is kept and no `total_count` is
    consulted — the feeds carry no change stamp to follow (every row of I2520
    says `2015-01-22`) and the count lies on some operations — so a run reads
    the whole feed every night. That costs the calls it costs; measured on
    the first cron night (2026-09-07), a full pass of the six feeds is 2,258
    windows, and the pool of three keys at 100 unfiltered calls an hour each
    walked it in 6 h 05 m, quota waits included, with no window refused.

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
    total = asyncio.run(sync_mfds_ledgers())
    print(f"Changed {total} ledger rows")
