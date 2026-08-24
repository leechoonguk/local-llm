# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.batch import Batch
from app.repositories.batch import BatchRepository
from app.schemas.batch import (
    BatchCreateInternal,
    BatchCreateRequest,
    BatchUpdateInternal,
    BatchUpdateRequest,
)


# ============================================================
# Classes
# ============================================================

class BatchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.batch_repository = BatchRepository(session)

    async def get_batch(self, batch_id: UUID) -> Batch:
        batch = await self.batch_repository.get(batch_id)
        if batch is None:
            raise NotFoundError(batch_id)
        return batch

    async def list_batches(self, offset: int = 0, limit: int = 100) -> list[Batch]:
        return await self.batch_repository.list(offset, limit)

    async def find_stale(self, older_than: datetime) -> list[Batch]:
        """Return batches created before the given timestamp — used by batch jobs."""
        return await self.batch_repository.find_stale(older_than)

    async def create_batch(self, data: BatchCreateRequest, created_by: str) -> Batch:
        internal = BatchCreateInternal(**data.model_dump(), created_by=created_by)
        async with self.session.begin():
            batch = await self.batch_repository.create(internal)
            return batch

    async def update_batch(
        self, batch_id: UUID, data: BatchUpdateRequest, updated_by: str
    ) -> Batch:
        internal = BatchUpdateInternal(**data.model_dump(exclude_unset=True), updated_by=updated_by)
        async with self.session.begin():
            batch = await self.batch_repository.update(batch_id, internal)
            if batch is None:
                raise NotFoundError(batch_id)
            return batch

    async def delete_batch(self, batch_id: UUID) -> None:
        async with self.session.begin():
            if not await self.batch_repository.delete(batch_id):
                raise NotFoundError(batch_id)
