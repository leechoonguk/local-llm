# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch.step import BatchStep
from app.schemas.batch.step import (
    BatchStepCreateInternal,
    BatchStepUpdateInternal,
)


# ============================================================
# Classes
# ============================================================


class BatchStepRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, step_id: UUID) -> BatchStep | None:
        return await self.session.get(BatchStep, step_id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[BatchStep]:
        result = await self.session.execute(select(BatchStep).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def list_by_run(self, run_id: UUID, offset: int = 0, limit: int = 100) -> list[BatchStep]:
        """One run's units in the order they happened."""
        result = await self.session.execute(
            select(BatchStep)
            .where(BatchStep.run_id == run_id)
            .order_by(BatchStep.sequence)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_run(self, run_id: UUID) -> int:
        """How many rows the unwindowed `list_by_run` would return."""
        result = await self.session.execute(
            select(func.count()).select_from(BatchStep).where(BatchStep.run_id == run_id)
        )
        return result.scalar_one()

    async def create(self, data: BatchStepCreateInternal) -> BatchStep:
        row = BatchStep(**data.model_dump())
        self.session.add(row)
        await self.session.flush()
        return row

    async def update(self, step_id: UUID, data: BatchStepUpdateInternal) -> BatchStep | None:
        row = await self.session.get(BatchStep, step_id)
        if row is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        row.updated_at = datetime.now(UTC)
        await self.session.flush()
        return row

    async def delete(self, step_id: UUID) -> bool:
        row = await self.session.get(BatchStep, step_id)
        if row is None:
            return False
        await self.session.delete(row)
        return True
