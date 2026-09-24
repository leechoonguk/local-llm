# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from itertools import count
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.core.exceptions import IntegrationError
from app.core.integration import IntegrationPage, window_rows
from app.core.ledger import Feed
from app.services.batch.run import current_run_id
from app.services.batch.step import BatchStepService
from app.services.integration.operation import IntegrationOperationService


# ============================================================
# Constants
# ============================================================

logger = structlog.get_logger(__name__)


# ============================================================
# Functions
# ============================================================


async def sync_ledger(
    provider_code: str,
    feed: Feed,
    synced_by: str,
    *,
    page_size: int,
    end_codes: frozenset[str],
) -> int:
    """Walk one feed whole and make one ledger equal to it; return the rows written.

    This is the body every ledger job shares, and all a job adds is which
    provider, which operation, which ledger and how wide a window
    (rule://backend-ledger). One job is one ledger because 식품안전나라 is shut
    09:00-19:00 KST: 18 hours of walking does not fit one night, so the feeds
    are laid across the nights of a weekend as separate schedule rows rather
    than queued inside one run.

    The ledger session is pinned to one connection because the stage a pass
    fills is a TEMP table, and a TEMP table lives on the connection that
    created it. The calls get a session of their own: their configuration
    reads and call logs must not share a transaction with the stage.

    A failure - the provider refused, or the pass came back under the floor -
    leaves the ledger as it was and ends the run. There is nothing to go on
    to: the other ledgers are other jobs, other runs, and tonight's for them
    is unaffected.
    """
    run_id = current_run_id.get()
    # Steps number the windows this run asked for: two steps sharing a
    # sequence is a UNIQUE error, and `integration_call_id` points at the call.
    sequence = count(1)
    async with (
        engine.connect() as connection,
        AsyncSession(connection) as ledger_session,
        AsyncSession(engine) as call_session,
    ):
        integration_operation_service = IntegrationOperationService(call_session)
        segmentation = await integration_operation_service.segmentation_of(
            provider_code, feed.operation_code
        )
        pages = (
            _walk_segments(
                integration_operation_service,
                provider_code,
                feed.operation_code,
                segmentation,
                synced_by,
                end_codes,
            )
            if segmentation is not None
            else integration_operation_service.walk_operation(
                provider_code,
                feed.operation_code,
                actor=synced_by,
                end_codes=end_codes,
            )
        )
        recorded = _record_pages(
            pages,
            run_id,
            sequence,
            integration_operation_service,
            synced_by,
            page_size,
        )
        _, written = await feed.replace(feed.service(ledger_session), recorded, synced_by)
    return written


async def _walk_segments(
    integration_operation_service: IntegrationOperationService,
    provider_code: str,
    operation_code: str,
    segmentation: tuple[str, list[str]],
    synced_by: str,
    end_codes: frozenset[str],
) -> AsyncIterator[IntegrationPage]:
    """Every window of every value of a feed's coordinate, in one stream.

    Which values exist is the configuration's to say and the provider's to
    confirm: each configured value is asked for a single row first, and only the
    ones that answer are walked. The pages of every value land in the caller's
    one stage, so the ledger is replaced once with the whole feed - the
    coordinate is how the feed is addressed, not which part of it is wanted.
    """
    segment_key, _ = segmentation
    for value in await _segment_values(
        integration_operation_service, provider_code, operation_code, segmentation, synced_by
    ):
        async for page in integration_operation_service.walk_operation(
            provider_code,
            operation_code,
            actor=synced_by,
            end_codes=end_codes,
            segment={segment_key: value},
        ):
            yield page


async def _segment_values(
    integration_operation_service: IntegrationOperationService,
    provider_code: str,
    operation_code: str,
    segmentation: tuple[str, list[str]],
    synced_by: str,
) -> list[str]:
    """The configured coordinate values this feed answers anything for, in order.

    A configured value the service does not publish - one listed ahead of the
    portal opening it - costs one window of one row and is skipped.
    """
    segment_key, candidates = segmentation
    values: list[str] = []
    for candidate in candidates:
        total = await integration_operation_service.segment_total(
            provider_code,
            operation_code,
            {segment_key: candidate},
            actor=synced_by,
        )
        if total > 0:
            values.append(candidate)
    logger.info(
        "batch.ledger.segments",
        operation=operation_code,
        segment=segment_key,
        values=values,
    )
    return values


async def _record_pages(
    pages: AsyncIterator[IntegrationPage],
    run_id: UUID | None,
    sequence: Iterator[int],
    integration_operation_service: IntegrationOperationService,
    synced_by: str,
    page_size: int,
) -> AsyncIterator[list[object]]:
    """Hand each page on to the ledger, writing one step per window as it passes.

    Either ending writes a step: the run's own row only says the night failed,
    and the window is the fact a reader needs. A refusal arrives before the
    walk could say which window it was asking for, so the step names the one
    after the last page - which is the window the walk asks for after a full
    page, always - and points at the call log row through the service, since
    the raise carried no return value.
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
                synced_by,
                received=len(page.records),
                integration_call_id=page.call_id,
            )
            yield page.records
    except IntegrationError as exc:
        await _record_step(
            run_id,
            next(sequence),
            (last_row + 1, last_row + page_size),
            0,
            synced_by,
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
    synced_by: str,
    *,
    received: int | None = None,
    integration_call_id: UUID | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    """Record one window, if this job is running under a scheduled run.

    A job started by hand has no run in context and writes no step: a step
    without a run has nothing to belong to, and inventing one would put a run
    in the log that no schedule ever fired. `written` is left empty on purpose:
    a ledger is written over per pass, not per window.
    """
    if run_id is None:
        return
    async with AsyncSession(engine) as session:
        batch_step_service = BatchStepService(session)
        await batch_step_service.create_finished_step(
            run_id,
            step,
            duration_ms,
            synced_by,
            range_start=rows[0],
            range_end=rows[1],
            received=received,
            integration_call_id=integration_call_id,
            error_code=error_code,
            error_detail=error_detail,
        )
