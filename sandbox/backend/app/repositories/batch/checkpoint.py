# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch.checkpoint import BatchCheckpoint
from app.schemas.batch.checkpoint import (
    BatchCheckpointCreateInternal,
    BatchCheckpointUpdateInternal,
)


# ============================================================
# Classes
# ============================================================


class BatchCheckpointRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, checkpoint_id: UUID) -> BatchCheckpoint | None:
        return await self.session.get(BatchCheckpoint, checkpoint_id)

    async def get_by_source_code(self, source_code: str) -> BatchCheckpoint | None:
        """The resume point of one external source — the sync's only lookup."""
        result = await self.session.execute(
            select(BatchCheckpoint).where(BatchCheckpoint.source_code == source_code)
        )
        return result.scalar_one_or_none()

    async def list(self, offset: int = 0, limit: int = 100) -> list[BatchCheckpoint]:
        result = await self.session.execute(select(BatchCheckpoint).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def create(self, data: BatchCheckpointCreateInternal) -> BatchCheckpoint:
        checkpoint = BatchCheckpoint(**data.model_dump())
        self.session.add(checkpoint)
        await self.session.flush()
        return checkpoint

    async def update(
        self, checkpoint_id: UUID, data: BatchCheckpointUpdateInternal
    ) -> BatchCheckpoint | None:
        checkpoint = await self.session.get(BatchCheckpoint, checkpoint_id)
        if checkpoint is None:
            return None
        return await self.update_row(checkpoint, data)

    async def update_row(
        self, checkpoint: BatchCheckpoint, data: BatchCheckpointUpdateInternal
    ) -> BatchCheckpoint:
        """Update a row the caller already loaded.

        The sync reaches this one: it has just looked the row up by source
        code, inside the same transaction, so re-reading it by id would only
        add a lookup that cannot fail — and a `None` branch no test can reach.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(checkpoint, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        checkpoint.updated_at = datetime.now(UTC)
        await self.session.flush()
        return checkpoint

    async def delete(self, checkpoint_id: UUID) -> bool:
        checkpoint = await self.session.get(BatchCheckpoint, checkpoint_id)
        if checkpoint is None:
            return False
        await self.session.delete(checkpoint)
        return True
