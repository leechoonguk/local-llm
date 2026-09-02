# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch.schedule import BatchSchedule
from app.schemas.batch.schedule import BatchCreateInternal, BatchUpdateInternal


# ============================================================
# Classes
# ============================================================


class BatchScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, batch_id: UUID) -> BatchSchedule | None:
        return await self.session.get(BatchSchedule, batch_id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[BatchSchedule]:
        result = await self.session.execute(select(BatchSchedule).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def count(self) -> int:
        """How many rows the unwindowed `list` would return."""
        result = await self.session.execute(select(func.count()).select_from(BatchSchedule))
        return result.scalar_one()

    async def list_enabled(self) -> list[BatchSchedule]:
        """Every job that should be running — the scheduler's whole input.

        Unpaged on purpose: a paged read would schedule the first page and
        leave the rest silently stopped after a restart.
        """
        result = await self.session.execute(
            select(BatchSchedule).where(BatchSchedule.enabled.is_(True))
        )
        return list(result.scalars().all())

    async def create(self, data: BatchCreateInternal) -> BatchSchedule:
        batch = BatchSchedule(**data.model_dump())
        self.session.add(batch)
        await self.session.flush()
        return batch

    async def update(self, batch_id: UUID, data: BatchUpdateInternal) -> BatchSchedule | None:
        batch = await self.session.get(BatchSchedule, batch_id)
        if batch is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(batch, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        batch.updated_at = datetime.now(UTC)
        await self.session.flush()
        return batch

    async def delete(self, batch_id: UUID) -> bool:
        batch = await self.session.get(BatchSchedule, batch_id)
        if batch is None:
            return False
        await self.session.delete(batch)
        return True
