# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.notice import Notice
from app.repositories.notice import NoticeRepository
from app.schemas.notice import (
    NoticeCreateInternal,
    NoticeCreateRequest,
    NoticeUpdateInternal,
    NoticeUpdateRequest,
)


# ============================================================
# Classes
# ============================================================

class NoticeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.notice_repository = NoticeRepository(session)

    async def get_notice(self, notice_id: UUID) -> Notice:
        notice = await self.notice_repository.get(notice_id)
        if notice is None:
            raise NotFoundError(notice_id)
        return notice

    async def list_notices(self, offset: int = 0, limit: int = 100) -> list[Notice]:
        return await self.notice_repository.list(offset, limit)

    async def find_stale(self, older_than: datetime) -> list[Notice]:
        """Return notices created before the given timestamp — used by batch jobs."""
        return await self.notice_repository.find_stale(older_than)

    async def create_notice(
        self, data: NoticeCreateRequest, created_by: str
    ) -> Notice:
        internal = NoticeCreateInternal(**data.model_dump(), created_by=created_by)
        async with self.session.begin():
            return await self.notice_repository.create(internal)

    async def update_notice(
        self, notice_id: UUID, data: NoticeUpdateRequest, updated_by: str
    ) -> Notice:
        internal = NoticeUpdateInternal(
            **data.model_dump(exclude_unset=True), updated_by=updated_by
        )
        async with self.session.begin():
            notice = await self.notice_repository.update(notice_id, internal)
            if notice is None:
                raise NotFoundError(notice_id)
            return notice

    async def delete_notice(self, notice_id: UUID) -> None:
        async with self.session.begin():
            if not await self.notice_repository.delete(notice_id):
                raise NotFoundError(notice_id)
