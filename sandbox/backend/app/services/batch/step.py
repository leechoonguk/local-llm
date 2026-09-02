# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.batch.step import BatchStep
from app.repositories.batch.step import BatchStepRepository
from app.schemas.batch.step import (
    FAILED,
    SUCCEEDED,
    BatchStepCreateInternal,
    BatchStepCreateRequest,
    BatchStepUpdateInternal,
    BatchStepUpdateRequest,
)


# ============================================================
# Classes
# ============================================================


class BatchStepService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.batch_step_repository = BatchStepRepository(session)

    async def get_step(self, step_id: UUID) -> BatchStep:
        step = await self.batch_step_repository.get(step_id)
        if step is None:
            raise NotFoundError(step_id)
        return step

    async def list_steps(self, offset: int = 0, limit: int = 100) -> list[BatchStep]:
        return await self.batch_step_repository.list(offset, limit)

    async def count_run_steps(self, run_id: UUID) -> int:
        """The collection's size, for the page the caller just read."""
        return await self.batch_step_repository.count_by_run(run_id)

    async def list_run_steps(
        self, run_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[BatchStep]:
        """One run's units, in the order they happened."""
        return await self.batch_step_repository.list_by_run(run_id, offset, limit)

    async def create_finished_step(
        self,
        run_id: UUID,
        sequence: int,
        duration_ms: int,
        created_by: str,
        *,
        range_start: int | None = None,
        range_end: int | None = None,
        received: int | None = None,
        written: int | None = None,
        integration_call_id: UUID | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> BatchStep:
        """Record a unit that ended, in whichever outcome.

        The status is derived from the error rather than passed in: a caller
        that reports an error and calls the step a success is stating two
        things at once, and the log would keep the wrong one.
        """
        return await self._create_step(
            BatchStepCreateRequest(
                run_id=run_id,
                sequence=sequence,
                status=FAILED if error_code is not None else SUCCEEDED,
                range_start=range_start,
                range_end=range_end,
                received=received,
                written=written,
                duration_ms=duration_ms,
                integration_call_id=integration_call_id,
                error_code=error_code,
                error_detail=error_detail,
            ),
            created_by=created_by,
        )

    async def update_step(
        self, step_id: UUID, data: BatchStepUpdateRequest, updated_by: str
    ) -> BatchStep:
        internal = BatchStepUpdateInternal(
            **data.model_dump(exclude_unset=True), updated_by=updated_by
        )
        async with self.session.begin():
            step = await self.batch_step_repository.update(step_id, internal)
            if step is None:
                raise NotFoundError(step_id)
            return step

    async def delete_step(self, step_id: UUID) -> None:
        async with self.session.begin():
            if not await self.batch_step_repository.delete(step_id):
                raise NotFoundError(step_id)

    async def _create_step(self, data: BatchStepCreateRequest, created_by: str) -> BatchStep:
        internal = BatchStepCreateInternal(**data.model_dump(), created_by=created_by)
        async with self.session.begin():
            return await self.batch_step_repository.create(internal)
