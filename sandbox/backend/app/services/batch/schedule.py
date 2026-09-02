# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.batch.schedule import BatchSchedule
from app.repositories.batch.schedule import BatchScheduleRepository
from app.schemas.batch.schedule import (
    BatchCreateInternal,
    BatchCreateRequest,
    BatchUpdateInternal,
    BatchUpdateRequest,
)


# ============================================================
# Classes
# ============================================================


class BatchScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.batch_schedule_repository = BatchScheduleRepository(session)

    async def get_batch(self, batch_id: UUID) -> BatchSchedule:
        batch = await self.batch_schedule_repository.get(batch_id)
        if batch is None:
            raise NotFoundError(batch_id)
        return batch

    async def count_batches(self) -> int:
        """The collection's size, for the page the caller just read."""
        return await self.batch_schedule_repository.count()

    async def list_batches(self, offset: int = 0, limit: int = 100) -> list[BatchSchedule]:
        return await self.batch_schedule_repository.list(offset, limit)

    async def list_enabled_batches(self) -> list[BatchSchedule]:
        """Return every enabled job — the schedule a starting process loads."""
        return await self.batch_schedule_repository.list_enabled()

    async def create_batch(self, data: BatchCreateRequest, created_by: str) -> BatchSchedule:
        internal = BatchCreateInternal(**data.model_dump(), created_by=created_by)
        async with self.session.begin():
            batch = await self.batch_schedule_repository.create(internal)
            return batch

    async def update_batch(
        self, batch_id: UUID, data: BatchUpdateRequest, updated_by: str
    ) -> BatchSchedule:
        internal = BatchUpdateInternal(**data.model_dump(exclude_unset=True), updated_by=updated_by)
        async with self.session.begin():
            batch = await self.batch_schedule_repository.update(batch_id, internal)
            if batch is None:
                raise NotFoundError(batch_id)
            return batch

    async def delete_batch(self, batch_id: UUID) -> None:
        async with self.session.begin():
            if not await self.batch_schedule_repository.delete(batch_id):
                raise NotFoundError(batch_id)
