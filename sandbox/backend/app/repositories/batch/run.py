# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch.run import BatchRun
from app.schemas.batch.run import (
    RUNNING,
    BatchRunCreateInternal,
    BatchRunUpdateInternal,
)


# ============================================================
# Classes
# ============================================================


class BatchRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, run_id: UUID) -> BatchRun | None:
        return await self.session.get(BatchRun, run_id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[BatchRun]:
        result = await self.session.execute(select(BatchRun).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def list_unfinished(self) -> list[BatchRun]:
        """Every run still marked RUNNING — what a restart has to settle.

        Unpaged on purpose: a page would leave the rest claiming to be running
        for as long as the table lives, and nobody reads a dashboard twice.
        """
        result = await self.session.execute(select(BatchRun).where(BatchRun.status == RUNNING))
        return list(result.scalars().all())

    async def list_by_batch(
        self, batch_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[BatchRun]:
        """One schedule's executions, newest first.

        Descending because the question this table answers is "what happened
        last night", and page one must be the night in question.
        """
        result = await self.session.execute(
            select(BatchRun)
            .where(BatchRun.batch_id == batch_id)
            .order_by(BatchRun.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_batch(self, batch_id: UUID) -> int:
        """How many rows the unwindowed `list_by_batch` would return."""
        result = await self.session.execute(
            select(func.count()).select_from(BatchRun).where(BatchRun.batch_id == batch_id)
        )
        return result.scalar_one()

    async def find_finished_before(self, older_than: datetime) -> list[BatchRun]:
        """Runs whose ending is older than the cutoff — retention's whole input.

        Keyed on `finished_at`, not `created_at`: a run's age is when it ended,
        and `RUNNING` rows have no ending — so a live run cannot be purged by
        construction, not by a filter someone must remember.
        """
        result = await self.session.execute(
            select(BatchRun).where(BatchRun.finished_at < older_than)
        )
        return list(result.scalars().all())

    async def create(self, data: BatchRunCreateInternal) -> BatchRun:
        row = BatchRun(**data.model_dump())
        self.session.add(row)
        await self.session.flush()
        return row

    async def update(self, run_id: UUID, data: BatchRunUpdateInternal) -> BatchRun | None:
        row = await self.session.get(BatchRun, run_id)
        if row is None:
            return None
        return await self.update_row(row, data)

    async def update_row(self, row: BatchRun, data: BatchRunUpdateInternal) -> BatchRun:
        """Update a row the caller already loaded.

        The state machine reads the run to measure its duration and writes it
        in the same transaction, so re-reading by id would add a lookup that
        cannot fail — and a `None` branch no test can reach.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        row.updated_at = datetime.now(UTC)
        await self.session.flush()
        return row

    async def delete(self, run_id: UUID) -> bool:
        row = await self.session.get(BatchRun, run_id)
        if row is None:
            return False
        await self.session.delete(row)
        return True
