# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch
from app.schemas.batch import BatchCreateInternal, BatchUpdateInternal


# ============================================================
# Classes
# ============================================================

class BatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, batch_id: UUID) -> Batch | None:
        return await self.session.get(Batch, batch_id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[Batch]:
        result = await self.session.execute(select(Batch).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def list_enabled(self) -> list[Batch]:
        """Every job that should be running — the scheduler's whole input.

        Unpaged on purpose: a paged read would schedule the first page and
        leave the rest silently stopped after a restart.
        """
        result = await self.session.execute(select(Batch).where(Batch.enabled.is_(True)))
        return list(result.scalars().all())

    async def find_stale(self, older_than: datetime) -> list[Batch]:
        result = await self.session.execute(select(Batch).where(Batch.created_at < older_than))
        return list(result.scalars().all())

    async def create(self, data: BatchCreateInternal) -> Batch:
        batch = Batch(**data.model_dump())
        self.session.add(batch)
        await self.session.flush()
        return batch

    async def update(self, batch_id: UUID, data: BatchUpdateInternal) -> Batch | None:
        batch = await self.session.get(Batch, batch_id)
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
        batch = await self.session.get(Batch, batch_id)
        if batch is None:
            return False
        await self.session.delete(batch)
        return True
