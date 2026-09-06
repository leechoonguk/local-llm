# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.batch.checkpoint import BatchCheckpoint
from app.repositories.batch.checkpoint import BatchCheckpointRepository
from app.schemas.batch.checkpoint import (
    BatchCheckpointCreateInternal,
    BatchCheckpointCreateRequest,
    BatchCheckpointUpdateInternal,
    BatchCheckpointUpdateRequest,
)


# ============================================================
# Classes
# ============================================================


class BatchCheckpointService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.batch_checkpoint_repository = BatchCheckpointRepository(session)

    async def get_checkpoint(self, checkpoint_id: UUID) -> BatchCheckpoint:
        checkpoint = await self.batch_checkpoint_repository.get(checkpoint_id)
        if checkpoint is None:
            raise NotFoundError(checkpoint_id)
        return checkpoint

    async def list_checkpoints(self, offset: int = 0, limit: int = 100) -> list[BatchCheckpoint]:
        return await self.batch_checkpoint_repository.list(offset, limit)

    async def find_checkpoint(self, source_code: str) -> BatchCheckpoint | None:
        """Where this source stopped, or None if nothing has recorded a position.

        The row rather than the offset: a resumable walk needs both halves of
        the position — the offset it would continue at, and the key of the
        record that offset was measured from — and handing back only the number
        would make every caller ask a second question to find out whether the
        number still means anything.

        A source that does not page by rows (a purge job's position is a cutoff
        it recomputes from the clock) has a row with both halves NULL, and a
        source nobody has read has no row at all. Neither absence is this
        layer's to interpret: the caller knows what its own first window is.
        """
        return await self.batch_checkpoint_repository.get_by_source_code(source_code)

    async def create_checkpoint(
        self, data: BatchCheckpointCreateRequest, created_by: str
    ) -> BatchCheckpoint:
        internal = BatchCheckpointCreateInternal(**data.model_dump(), created_by=created_by)
        async with self.session.begin():
            return await self.batch_checkpoint_repository.create(internal)

    async def update_checkpoint(
        self, checkpoint_id: UUID, data: BatchCheckpointUpdateRequest, updated_by: str
    ) -> BatchCheckpoint:
        internal = BatchCheckpointUpdateInternal(
            **data.model_dump(exclude_unset=True), updated_by=updated_by
        )
        async with self.session.begin():
            checkpoint = await self.batch_checkpoint_repository.update(checkpoint_id, internal)
            if checkpoint is None:
                raise NotFoundError(checkpoint_id)
            return checkpoint

    async def update_resume_point(
        self,
        source_code: str,
        resume_position: int,
        resume_key: str | None,
        updated_by: str,
    ) -> BatchCheckpoint:
        """Record where the next window starts — creating the row on first use.

        The offset and the key it was measured from are written together, in one
        transaction, because a position is both halves: an offset stored beside
        a key from a different page is worse than no key at all — the next run
        would compare against the wrong record and restart a walk that was fine.

        Written after every page rather than at the end of a pass: a run that
        dies mid-pass must cost the pages it had not read, not the ones it had.
        The ledger write and this write are separate transactions, so a crash
        between them re-reads one window — which the ledger's upsert absorbs.
        Losing checkpoint is recoverable; claiming checkpoint that was never
        written is not, so the order is ledger first, offset second.
        """
        async with self.session.begin():
            checkpoint = await self.batch_checkpoint_repository.get_by_source_code(source_code)
            if checkpoint is None:
                return await self.batch_checkpoint_repository.create(
                    BatchCheckpointCreateInternal(
                        source_code=source_code,
                        resume_position=resume_position,
                        resume_key=resume_key,
                        created_by=updated_by,
                    )
                )
            return await self.batch_checkpoint_repository.update_row(
                checkpoint,
                BatchCheckpointUpdateInternal(
                    resume_position=resume_position,
                    resume_key=resume_key,
                    updated_by=updated_by,
                ),
            )

    async def delete_checkpoint(self, checkpoint_id: UUID) -> None:
        async with self.session.begin():
            if not await self.batch_checkpoint_repository.delete(checkpoint_id):
                raise NotFoundError(checkpoint_id)
