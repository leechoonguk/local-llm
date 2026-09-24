# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from asyncio import AbstractEventLoop, Lock, get_running_loop
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import UUID
from weakref import WeakKeyDictionary

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.batch.run import BatchRun
from app.repositories.batch.run import BatchRunRepository
from app.schemas.batch.run import (
    RUNNING,
    BatchRunCreateInternal,
    BatchRunCreateRequest,
    BatchRunStatus,
    BatchRunUpdateInternal,
    BatchRunUpdateRequest,
    BatchTrigger,
)


# ============================================================
# Constants
# ============================================================

INTERRUPTED = "INTERRUPTED"

# The run a job is executing inside, for the steps it wants to record. A
# contextvar rather than an argument: `BATCH_JOBS` calls a job with none, and
# widening that signature would put the log in every job's contract instead of
# leaving it optional. A job started by hand simply finds `None` here.
#
# It lives with the run rather than with the scheduler because the scheduler
# imports the jobs, and a job importing the scheduler back is a cycle.
current_run_id: ContextVar[UUID | None] = ContextVar("current_run_id", default=None)

#: One gate per event loop. An `asyncio.Lock` binds to the loop that first
#: acquires it and raises on any other, and a module-level lock outlives the
#: loop under a test suite that opens one per test. Weakly keyed, so a finished
#: loop takes its gate with it.
_start_gates: WeakKeyDictionary[AbstractEventLoop, Lock] = WeakKeyDictionary()


#: Held while a run row is opened, and while a job reads the rows to decide
#: whether it has anything to do. The two readings have to be ordered or they
#: are not readings at all: measured 2026-09-15, three ledger jobs and the
#: derive job were fired in the same millisecond, every row was opened after
#: the derive job had looked, and the derive job rebuilt fifteen tables against
#: ledgers that were being replaced under it. Process-local, like the run map
#: the scheduler cancels from - a run of another process is another process's.
def run_start_gate() -> Lock:
    """This loop's start gate, made on first use."""
    loop = get_running_loop()
    gate = _start_gates.get(loop)
    if gate is None:
        gate = _start_gates.setdefault(loop, Lock())
    return gate


# What a swept run says happened. There is no writer for a process that was
# killed, so the sweep speaks for it — and says only what it knows.
INTERRUPTED_DETAIL = "The process ended before the run reported an outcome."


# ============================================================
# Classes
# ============================================================


class BatchRunService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.batch_run_repository = BatchRunRepository(session)

    async def get_run(self, run_id: UUID) -> BatchRun:
        run = await self.batch_run_repository.get(run_id)
        if run is None:
            raise NotFoundError(run_id)
        return run

    async def list_runs(self, offset: int = 0, limit: int = 100) -> list[BatchRun]:
        return await self.batch_run_repository.list(offset, limit)

    async def count_schedule_runs(self, batch_id: UUID) -> int:
        """The collection's size, for the page the caller just read."""
        return await self.batch_run_repository.count_by_batch(batch_id)

    async def list_schedule_runs(
        self, batch_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[BatchRun]:
        """One schedule's executions, newest first."""
        return await self.batch_run_repository.list_by_batch(batch_id, offset, limit)

    async def find_finished_before(self, older_than: datetime) -> list[BatchRun]:
        """Runs that ended before the cutoff — what the purge job deletes."""
        return await self.batch_run_repository.find_finished_before(older_than)

    async def create_started_run(
        self, batch_id: UUID | None, code: str, trigger: BatchTrigger, triggered_by: str
    ) -> BatchRun:
        """Open a run at the moment the job starts.

        Written before the job's first line so that a process which dies
        immediately still leaves the fact that it started. The row is the only
        evidence a crashed run ever existed.
        """
        return await self._create_run(
            BatchRunCreateRequest(
                batch_id=batch_id,
                code=code,
                status=RUNNING,
                trigger=trigger,
                triggered_by=triggered_by,
                started_at=datetime.now(UTC),
            ),
            created_by=triggered_by,
        )

    async def update_run(
        self, run_id: UUID, data: BatchRunUpdateRequest, updated_by: str
    ) -> BatchRun:
        internal = BatchRunUpdateInternal(
            **data.model_dump(exclude_unset=True), updated_by=updated_by
        )
        async with self.session.begin():
            run = await self.batch_run_repository.update(run_id, internal)
            if run is None:
                raise NotFoundError(run_id)
            return run

    async def update_finished_run(
        self,
        run_id: UUID,
        status: BatchRunStatus,
        updated_by: str,
        *,
        result: int | None = None,
        stopped_by: str | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> BatchRun:
        """Close a run with the ending it actually had.

        The duration is measured from the stored `started_at` rather than
        handed in: the caller that knows the ending is not always the one that
        knew the beginning, and two clocks would drift apart in the log.
        """
        async with self.session.begin():
            return await self._close(
                run_id,
                status,
                updated_by,
                result=result,
                stopped_by=stopped_by,
                error_code=error_code,
                error_detail=error_detail,
            )

    async def update_interrupted_runs(self, updated_by: str) -> int:
        """Settle runs whose process never came back; report how many.

        Called at startup, when no run of this process exists yet: anything
        still `RUNNING` belongs to a process that is gone. Without this a
        killed run claims to be running forever, and "is the sync stuck?"
        becomes unanswerable from the data.
        """
        async with self.session.begin():
            unfinished = await self.batch_run_repository.list_unfinished()
            for run in unfinished:
                await self._close(
                    run.id,
                    INTERRUPTED,
                    updated_by,
                    error_code="batch_run_interrupted",
                    error_detail=INTERRUPTED_DETAIL,
                )
            return len(unfinished)

    async def list_running_codes(self, excluding: UUID | None = None) -> set[str]:
        """The job codes with an execution in flight - what a job that depends on others asks.

        A derivation reads the ledgers other jobs write, and a ledger mid-pass
        is fine to read (a pass lands in one short transaction) but its night
        is not over: the derivation would be rebuilt against last night's rows
        and stand until tomorrow. So it asks, and waits its next turn instead.
        """
        unfinished = await self.batch_run_repository.list_unfinished()
        # The asking job's own run is in flight by definition - it is the one
        # asking - so it is not an answer to "is anything else running".
        return {run.code for run in unfinished if run.id != excluding}

    async def delete_run(self, run_id: UUID) -> None:
        async with self.session.begin():
            if not await self.batch_run_repository.delete(run_id):
                raise NotFoundError(run_id)

    async def _create_run(self, data: BatchRunCreateRequest, created_by: str) -> BatchRun:
        internal = BatchRunCreateInternal(**data.model_dump(), created_by=created_by)
        async with self.session.begin():
            return await self.batch_run_repository.create(internal)

    async def _close(
        self,
        run_id: UUID,
        status: BatchRunStatus,
        updated_by: str,
        *,
        result: int | None = None,
        stopped_by: str | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> BatchRun:
        """Write one ending, inside the caller's transaction.

        Reading the row and writing it are one step here: a read on this
        session autobegins a transaction, so a nested `begin()` in a second
        method raises rather than nesting. The sweep needs many endings in one
        boundary anyway.
        """
        run = await self.batch_run_repository.get(run_id)
        if run is None:
            raise NotFoundError(run_id)
        if run.status != RUNNING:
            # An ending is written once. A stop recorded from the request and a
            # job that finished anyway would otherwise overwrite each other, and
            # the log would keep whichever lost the race.
            return run
        finished_at = datetime.now(UTC)
        started_at = run.started_at
        if started_at.tzinfo is None:
            # SQLite hands `DateTime(timezone=True)` back without its offset;
            # the column is written in UTC, so that is what a naive value means.
            started_at = started_at.replace(tzinfo=UTC)
        return await self.batch_run_repository.update_row(
            run,
            BatchRunUpdateInternal(
                status=status,
                finished_at=finished_at,
                duration_ms=round((finished_at - started_at).total_seconds() * 1000),
                result=result,
                stopped_by=stopped_by,
                error_code=error_code,
                error_detail=error_detail,
                updated_by=updated_by,
            ),
        )
