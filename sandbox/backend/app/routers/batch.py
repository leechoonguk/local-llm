# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.core.cache import scoped_cache_key
from app.core.exceptions import ConflictError, NotFoundError
from app.core.settings import settings
from app.dependencies.auth import CurrentUserDep
from app.dependencies.core import CacheDep, SchedulerDep
from app.dependencies.query import LimitQuery, OffsetQuery
from app.dependencies.services import (
    BatchRunServiceDep,
    BatchScheduleServiceDep,
    BatchStepServiceDep,
)
from app.schemas.batch.run import BatchRunReadResponse
from app.schemas.batch.run import to_read_list as to_run_read_list
from app.schemas.batch.schedule import (
    BatchCreateRequest,
    BatchReadResponse,
    BatchRunRequest,
    BatchRunResponse,
    BatchUpdateRequest,
    to_read,
    to_read_list,
)
from app.schemas.batch.step import BatchStepReadResponse
from app.schemas.batch.step import to_read_list as to_step_read_list
from app.schemas.page import Page


# ============================================================
# Constants
# ============================================================

BATCH_CACHE_PREFIX = "batches"
BATCH_CACHE_TTL_SECONDS = 60


# ============================================================
# Router
# ============================================================

router = APIRouter(
    prefix="/batch",
    tags=["batch"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_batch(
    data: BatchCreateRequest,
    batch_schedule_service: BatchScheduleServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
    scheduler: SchedulerDep,
) -> BatchReadResponse:
    batch = await batch_schedule_service.create_batch(data, created_by=current_user.username)
    response = to_read(batch)
    if scheduler is not None:
        scheduler.sync(batch.id, batch.code, batch.cron, enabled=batch.enabled)
    if cache is not None:
        await cache.invalidate(BATCH_CACHE_PREFIX)
    return response


@router.get("/")
async def list_batches(
    batch_schedule_service: BatchScheduleServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
) -> Page[BatchReadResponse]:
    cache_key = scoped_cache_key(BATCH_CACHE_PREFIX, str(current_user.id), f"list:{offset}:{limit}")
    cached = await cache.get_json(cache_key) if cache is not None else None
    # The cached value is the whole answer, total included: caching the rows
    # alone would have made every cache hit cost the count query it saved.
    if isinstance(cached, dict):
        return Page[BatchReadResponse].model_validate(cached)

    response = Page(
        items=to_read_list(await batch_schedule_service.list_batches(offset, limit)),
        total=await batch_schedule_service.count_batches(),
    )
    if cache is not None:
        await cache.set_json(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=BATCH_CACHE_TTL_SECONDS,
        )
    return response


@router.get("/{batch_id}")
async def get_batch(
    batch_id: UUID,
    batch_schedule_service: BatchScheduleServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
) -> BatchReadResponse:
    cache_key = scoped_cache_key(BATCH_CACHE_PREFIX, str(current_user.id), f"detail:{batch_id}")
    cached = await cache.get_json(cache_key) if cache is not None else None
    if isinstance(cached, dict):
        return BatchReadResponse.model_validate(cached)

    response = to_read(await batch_schedule_service.get_batch(batch_id))
    if cache is not None:
        await cache.set_json(
            cache_key, response.model_dump(mode="json"), ttl_seconds=BATCH_CACHE_TTL_SECONDS
        )
    return response


@router.patch("/{batch_id}")
async def update_batch(
    batch_id: UUID,
    data: BatchUpdateRequest,
    batch_schedule_service: BatchScheduleServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
    scheduler: SchedulerDep,
) -> BatchReadResponse:
    batch = await batch_schedule_service.update_batch(
        batch_id, data, updated_by=current_user.username
    )
    response = to_read(batch)
    # The row is the schedule, so the write is not finished until the running
    # process agrees with it: a cron edit or `enabled=false` that only landed in
    # the table would keep firing the old trigger until the next restart.
    if scheduler is not None:
        scheduler.sync(batch.id, batch.code, batch.cron, enabled=batch.enabled)
    if cache is not None:
        await cache.invalidate(BATCH_CACHE_PREFIX)
    return response


@router.delete("/{batch_id}")
async def delete_batch(
    batch_id: UUID,
    batch_schedule_service: BatchScheduleServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
    scheduler: SchedulerDep,
) -> dict[str, bool]:
    await batch_schedule_service.delete_batch(batch_id)
    if scheduler is not None:
        scheduler.remove(batch_id)
    if cache is not None:
        await cache.invalidate(BATCH_CACHE_PREFIX)
    return {"ok": True}


@router.post("/{batch_id}/run")
async def run_batch(
    batch_id: UUID,
    data: BatchRunRequest,
    batch_schedule_service: BatchScheduleServiceDep,
    current_user: CurrentUserDep,
    scheduler: SchedulerDep,
) -> BatchRunResponse:
    """Start or stop one execution — the schedule and `enabled` are untouched.

    One endpoint because the client states the execution state it wants:
    `running: true` fires the job now (409 while one is already in flight),
    `running: false` cancels the run in flight and is idempotent.

    A deactivated row may still be run by hand: `enabled` says whether the clock
    starts the job, not whether an operator may. A process without a scheduler
    (a web-only replica) answers 409 rather than accepting a run nothing would
    execute.
    """
    batch = await batch_schedule_service.get_batch(batch_id)
    if scheduler is None:
        raise ConflictError("No scheduler is running in this process")
    if data.running:
        scheduler.run_now(batch.id, batch.code, current_user.username)
    else:
        await scheduler.stop(batch.id, current_user.username)
    return BatchRunResponse(id=batch.id, code=batch.code, running=data.running)


@router.get("/{batch_id}/runs")
async def list_batch_runs(
    batch_id: UUID,
    batch_schedule_service: BatchScheduleServiceDep,
    batch_run_service: BatchRunServiceDep,
    current_user: CurrentUserDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
) -> Page[BatchRunReadResponse]:
    """One schedule's executions, newest first.

    Uncached on purpose: the rows are written by the scheduler, outside any
    HTTP request, so no write path could ever invalidate a cache — a cached
    answer here would report last night's failure as still running.

    The schedule is loaded first so an unknown id answers 404 rather than an
    empty history that reads as "never ran".
    """
    await batch_schedule_service.get_batch(batch_id)
    return Page(
        items=to_run_read_list(await batch_run_service.list_schedule_runs(batch_id, offset, limit)),
        total=await batch_run_service.count_schedule_runs(batch_id),
    )


@router.get("/{batch_id}/runs/{run_id}/steps")
async def list_batch_run_steps(
    batch_id: UUID,
    run_id: UUID,
    batch_run_service: BatchRunServiceDep,
    batch_step_service: BatchStepServiceDep,
    current_user: CurrentUserDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
) -> Page[BatchStepReadResponse]:
    """One run's units, in the order they happened.

    The run is loaded first so an unknown id answers 404, not an empty night.
    """
    run = await batch_run_service.get_run(run_id)
    if run.batch_id != batch_id:
        # The path claims a parentage the row does not have — answer as if the
        # run were absent rather than leaking another schedule's history.
        raise NotFoundError(run_id)
    return Page(
        items=to_step_read_list(await batch_step_service.list_run_steps(run_id, offset, limit)),
        total=await batch_step_service.count_run_steps(run_id),
    )
