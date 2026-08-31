# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.core.cache import scoped_cache_key
from app.core.settings import settings
from app.dependencies.auth import CurrentUserDep
from app.dependencies.core import CacheDep
from app.dependencies.query import LimitQuery, OffsetQuery
from app.dependencies.services import BatchServiceDep
from app.schemas.batch import (
    BatchCreateRequest,
    BatchReadResponse,
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
) -> BatchReadResponse:
    batch = await batch_service.create_batch(data, created_by=current_user.username)
    response = to_read(batch)
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
) -> BatchReadResponse:
    batch = await batch_service.update_batch(batch_id, data, updated_by=current_user.username)
    response = to_read(batch)
    if cache is not None:
        await cache.invalidate(BATCH_CACHE_PREFIX)
    return response


@router.delete("/{batch_id}")
async def delete_batch(
    batch_id: UUID, batch_service: BatchServiceDep, current_user: CurrentUserDep, cache: CacheDep
) -> dict[str, bool]:
    await batch_service.delete_batch(batch_id)
    if cache is not None:
        await cache.invalidate(BATCH_CACHE_PREFIX)
    return {"ok": True}
