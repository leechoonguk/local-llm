# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.core.cache import scoped_cache_key
from app.core.exceptions import ConflictError
from app.core.settings import settings
from app.dependencies.auth import CurrentUserDep
from app.dependencies.core import CacheDep, SchedulerDep
from app.dependencies.query import LimitQuery, OffsetQuery
from app.dependencies.services import BatchServiceDep
from app.schemas.batch import (
    BatchCreateRequest,
    BatchReadResponse,
    BatchRunRequest,
    BatchRunResponse,
    BatchUpdateRequest,
    to_read,
    to_read_list,
)


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
    batch_service: BatchServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
    scheduler: SchedulerDep,
) -> BatchReadResponse:
    batch = await batch_service.create_batch(data, created_by=current_user.username)
    response = to_read(batch)
    if scheduler is not None:
        scheduler.sync(batch.id, batch.code, batch.cron, enabled=batch.enabled)
    if cache is not None:
        await cache.invalidate(BATCH_CACHE_PREFIX)
    return response


@router.get("/")
async def list_batches(
    batch_service: BatchServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
) -> list[BatchReadResponse]:
    cache_key = scoped_cache_key(
        BATCH_CACHE_PREFIX, str(current_user.id), f"list:{offset}:{limit}"
    )
    cached = await cache.get_json(cache_key) if cache is not None else None
    if isinstance(cached, list):
        return [BatchReadResponse.model_validate(batch) for batch in cached]

    response = to_read_list(await batch_service.list_batches(offset, limit))
    if cache is not None:
        await cache.set_json(
            cache_key,
            [batch.model_dump(mode="json") for batch in response],
            ttl_seconds=BATCH_CACHE_TTL_SECONDS,
        )
    return response


@router.get("/{batch_id}")
async def get_batch(
    batch_id: UUID, batch_service: BatchServiceDep, current_user: CurrentUserDep, cache: CacheDep
) -> BatchReadResponse:
    cache_key = scoped_cache_key(BATCH_CACHE_PREFIX, str(current_user.id), f"detail:{batch_id}")
    cached = await cache.get_json(cache_key) if cache is not None else None
    if isinstance(cached, dict):
        return BatchReadResponse.model_validate(cached)

    response = to_read(await batch_service.get_batch(batch_id))
    if cache is not None:
        await cache.set_json(
            cache_key, response.model_dump(mode="json"), ttl_seconds=BATCH_CACHE_TTL_SECONDS
        )
    return response


@router.patch("/{batch_id}")
async def update_batch(
    batch_id: UUID,
    data: BatchUpdateRequest,
    batch_service: BatchServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
    scheduler: SchedulerDep,
) -> BatchReadResponse:
    batch = await batch_service.update_batch(batch_id, data, updated_by=current_user.username)
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
    batch_service: BatchServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
    scheduler: SchedulerDep,
) -> dict[str, bool]:
    await batch_service.delete_batch(batch_id)
    if scheduler is not None:
        scheduler.remove(batch_id)
    if cache is not None:
        await cache.invalidate(BATCH_CACHE_PREFIX)
    return {"ok": True}


@router.post("/{batch_id}/run")
async def run_batch(
    batch_id: UUID,
    data: BatchRunRequest,
    batch_service: BatchServiceDep,
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
    batch = await batch_service.get_batch(batch_id)
    if scheduler is None:
        raise ConflictError("No scheduler is running in this process")
    if data.running:
        scheduler.run_now(batch.id, batch.code)
    else:
        scheduler.stop(batch.id)
    return BatchRunResponse(id=batch.id, code=batch.code, running=data.running)
