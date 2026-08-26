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
from app.dependencies.services import NoticeServiceDep
from app.schemas.notice import (
    NoticeCreateRequest,
    NoticeReadResponse,
    NoticeUpdateRequest,
    to_read,
    to_read_list,
)


# ============================================================
# Constants
# ============================================================

NOTICE_CACHE_PREFIX = "notices"
NOTICE_CACHE_TTL_SECONDS = 60


# ============================================================
# Router
# ============================================================

router = APIRouter(
    prefix="/notice",
    tags=["notice"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_notice(
    data: NoticeCreateRequest,
    notice_service: NoticeServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
) -> NoticeReadResponse:
    notice = await notice_service.create_notice(data, created_by=current_user.username)
    response = to_read(notice)
    if cache is not None:
        await cache.invalidate(NOTICE_CACHE_PREFIX)
    return response


@router.get("/")
async def list_notices(
    notice_service: NoticeServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
) -> list[NoticeReadResponse]:
    cache_key = scoped_cache_key(
        NOTICE_CACHE_PREFIX, str(current_user.id), f"list:{offset}:{limit}"
    )
    cached = await cache.get_json(cache_key) if cache is not None else None
    if isinstance(cached, list):
        return [NoticeReadResponse.model_validate(n) for n in cached]

    response = to_read_list(await notice_service.list_notices(offset, limit))
    if cache is not None:
        await cache.set_json(
            cache_key,
            [n.model_dump(mode="json") for n in response],
            ttl_seconds=NOTICE_CACHE_TTL_SECONDS,
        )
    return response


@router.get("/{notice_id}")
async def get_notice(
    notice_id: UUID,
    notice_service: NoticeServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
) -> NoticeReadResponse:
    cache_key = scoped_cache_key(
        NOTICE_CACHE_PREFIX, str(current_user.id), f"detail:{notice_id}"
    )
    cached = await cache.get_json(cache_key) if cache is not None else None
    if isinstance(cached, dict):
        return NoticeReadResponse.model_validate(cached)

    response = to_read(await notice_service.get_notice(notice_id))
    if cache is not None:
        await cache.set_json(
            cache_key, response.model_dump(mode="json"), ttl_seconds=NOTICE_CACHE_TTL_SECONDS
        )
    return response


@router.put("/{notice_id}")
async def update_notice(
    notice_id: UUID,
    data: NoticeUpdateRequest,
    notice_service: NoticeServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
) -> NoticeReadResponse:
    notice = await notice_service.update_notice(notice_id, data, updated_by=current_user.username)
    response = to_read(notice)
    if cache is not None:
        await cache.invalidate(NOTICE_CACHE_PREFIX)
    return response


@router.delete("/{notice_id}")
async def delete_notice(
    notice_id: UUID,
    notice_service: NoticeServiceDep,
    current_user: CurrentUserDep,
    cache: CacheDep,
) -> dict[str, bool]:
    await notice_service.delete_notice(notice_id)
    if cache is not None:
        await cache.invalidate(NOTICE_CACHE_PREFIX)
    return {"ok": True}
