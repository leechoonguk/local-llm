# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notice import Notice
from app.schemas.notice import NoticeCreateInternal, NoticeUpdateInternal


# ============================================================
# Classes
# ============================================================

class NoticeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, notice_id: UUID) -> Notice | None:
        return await self.session.get(Notice, notice_id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[Notice]:
        result = await self.session.execute(select(Notice).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def find_stale(self, older_than: datetime) -> list[Notice]:
        result = await self.session.execute(select(Notice).where(Notice.created_at < older_than))
        return list(result.scalars().all())

    async def create(self, data: NoticeCreateInternal) -> Notice:
        notice = Notice(**data.model_dump())
        self.session.add(notice)
        await self.session.flush()
        return notice

    async def update(self, notice_id: UUID, data: NoticeUpdateInternal) -> Notice | None:
        notice = await self.session.get(Notice, notice_id)
        if notice is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(notice, field, value)
        notice.updated_at = datetime.now(UTC)
        await self.session.flush()
        return notice

    async def delete(self, notice_id: UUID) -> bool:
        notice = await self.session.get(Notice, notice_id)
        if notice is None:
            return False
        await self.session.delete(notice)
        return True
