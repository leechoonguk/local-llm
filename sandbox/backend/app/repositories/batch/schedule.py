# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sorting import ordered
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

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        code: str | None = None,
        sort: str | None = None,
        order: str = "asc",
    ) -> list[BatchSchedule]:
        query = ordered(
            _apply_filters(select(BatchSchedule), code),
            BatchSchedule,
            sort,
            order,
            BatchSchedule.id,
        )
        result = await self.session.execute(query.offset(offset).limit(limit))
        return list(result.scalars().all())

    async def count(self, code: str | None = None) -> int:
        """How many rows the unwindowed `list` would return, under the same filter."""
        query = _apply_filters(select(func.count()).select_from(BatchSchedule), code)
        result = await self.session.execute(query)
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


# ============================================================
# Functions
# ============================================================


def _apply_filters(query: Select[Any], code: str | None) -> Select[Any]:
    """Narrow a schedule query to the rows whose code contains `code`.

    One builder for the page and its count: two spellings of the same predicate
    is how a filtered list and its total start disagreeing. `ilike` (never
    `like`) so the match is case-insensitive on every backend, and the wildcards
    are added here so a caller never sends SQL syntax.
    """
    if code is None:
        return query
    return query.where(BatchSchedule.code.ilike(f"%{code}%"))
