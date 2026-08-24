# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.core.settings import settings
from app.dependencies.auth import CurrentUserDep
from app.dependencies.query import LimitQuery, OffsetQuery
from app.dependencies.services import UserServiceDep
from app.schemas.user import (
    UserCreateRequest,
    UserReadResponse,
    UserUpdateRequest,
    to_read,
    to_read_list,
)


# ============================================================
# Router
# ============================================================

router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreateRequest, user_service: UserServiceDep) -> UserReadResponse:
    user = await user_service.create_user(data, created_by="system")
    return to_read(user)


@router.get("/")
async def list_users(
    user_service: UserServiceDep,
    current_user: CurrentUserDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
) -> list[UserReadResponse]:
    return to_read_list(await user_service.list_users(offset, limit))


@router.get("/{user_id}")
async def get_user(
    user_id: UUID, user_service: UserServiceDep, current_user: CurrentUserDep
) -> UserReadResponse:
    user = await user_service.get_user(user_id)
    return to_read(user)


@router.put("/{user_id}")
async def update_user(
    user_id: UUID,
    data: UserUpdateRequest,
    user_service: UserServiceDep,
    current_user: CurrentUserDep,
) -> UserReadResponse:
    user = await user_service.update_user(user_id, data, updated_by=current_user.username)
    return to_read(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID, user_service: UserServiceDep, current_user: CurrentUserDep
) -> dict[str, bool]:
    await user_service.delete_user(user_id)
    return {"ok": True}
