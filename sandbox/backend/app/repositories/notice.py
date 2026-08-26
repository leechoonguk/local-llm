# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
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
        result = await self.session.execute(
            select(Notice)
            .order_by(Notice.pinned.desc(), Notice.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def find_stale(self, older_than: datetime) -> list[Notice]:
        result = await self.session.execute(select(Notice).where(Notice.created_at < older_than))
        return list(result.scalars().all())

    async def create(self, data: NoticeCreateInternal) -> Notice:
        notice = Notice(**data.model_dump())
        self.session.add(notice)
        try:
            await self.session.flush()
        except IntegrityError as err:
            await self.session.rollback()
            raise ConflictError(f"Notice title '{data.title}' already exists") from err
        return notice

    async def update(self, notice_id: UUID, data: NoticeUpdateInternal) -> Notice | None:
        notice = await self.session.get(Notice, notice_id)
        if notice is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(notice, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        notice.updated_at = datetime.now(UTC)
        try:
            await self.session.flush()
        except IntegrityError as err:
            await self.session.rollback()
            raise ConflictError(f"Notice title '{notice.title}' already exists") from err
        return notice

    async def delete(self, notice_id: UUID) -> bool:
        notice = await self.session.get(Notice, notice_id)
        if notice is None:
            return False
        await self.session.delete(notice)
        return True
