# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from asyncio import CancelledError, Task, current_task
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from types import MappingProxyType
from uuid import UUID

import structlog
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from app.batch.purge_expired_refreshes import purge_expired_refreshes
from app.batch.purge_old_batch_runs import purge_old_batch_runs
from app.batch.sync_food_barcode_ledger import sync_food_barcode_ledger
from app.batch.sync_food_item_report_ledger import sync_food_item_report_ledger
from app.batch.sync_food_item_report_raw_material_ledger import (
    sync_food_item_report_raw_material_ledger,
)
from app.batch.sync_food_nutrition_ledger import sync_food_nutrition_ledger
from app.batch.sync_food_raw_material_ledger import sync_food_raw_material_ledger
from app.core.database import engine
from app.core.exceptions import ConflictError
from app.schemas.batch.run import BatchRunStatus, BatchTrigger
from app.services.batch.run import BatchRunService, current_run_id


# ============================================================
# Constants
# ============================================================

type BatchJob = Callable[[], Awaitable[int]]

#: A run in flight and a code the registry does not carry are different answers
#: to "run this now", and an operator acts differently on each.
BATCH_ALREADY_RUNNING_CODE = "batch_already_running"

BATCH_JOB_UNREGISTERED_CODE = "batch_job_unregistered"

#: `settings.env == "test"` disables the scheduler, so a run request reaches a
#: process that would execute nothing.
SCHEDULER_UNAVAILABLE_CODE = "scheduler_unavailable"

# The only place a job code becomes runnable Python. A `batch` row names a key
# here, so adding a job is one function plus one row — the lifespan never grows
# a branch, and a code nothing implements is rejected at the API boundary
# instead of failing silently at 03:00.
BATCH_JOBS: Mapping[str, BatchJob] = MappingProxyType(
    {
        "purge_expired_refreshes": purge_expired_refreshes,
        "purge_old_batch_runs": purge_old_batch_runs,
        "sync_food_barcode_ledger": sync_food_barcode_ledger,
        "sync_food_item_report_ledger": sync_food_item_report_ledger,
        "sync_food_item_report_raw_material_ledger": sync_food_item_report_raw_material_ledger,
        "sync_food_nutrition_ledger": sync_food_nutrition_ledger,
        "sync_food_raw_material_ledger": sync_food_raw_material_ledger,
    }
)

# A restart across the scheduled minute must still run the job. One hour is the
# window in which a late run is worth more than a skipped one.
MISFIRE_GRACE_SECONDS = 3600

# A manual run carries its own scheduler id so it cannot evict the row's cron
# job — the two are different things and must be able to coexist.
MANUAL_RUN_SUFFIX = ":run-now"

# Who fired this execution, in the words the row stores.
CRON_TRIGGER: BatchTrigger = "CRON"

MANUAL_TRIGGER: BatchTrigger = "MANUAL"

SCHEDULER_ACTOR = "scheduler"


logger = structlog.get_logger(__name__)


# ============================================================
# Classes
# ============================================================


class BatchScheduler:
    """An APScheduler whose job table is the `batch` table.

    Nothing here decides *when* a job runs: every trigger is built from a row,
    so rescheduling is an UPDATE and deactivating a job is `enabled = false`.
    The scheduler is keyed on the row id rather than the job code, because one
    code may legitimately carry two schedules.

    Three verbs, three different meanings, deliberately not collapsed:

    | Verb | Acts on | Effect |
    |---|---|---|
    | `sync` / `remove` | the trigger | whether the row fires on its cron at all |
    | `run_now` | one execution | fire it once, outside the schedule |
    | `stop` | one execution | cancel the run that is in flight, trigger untouched |

    An execution is tracked by its own asyncio task, which is what makes
    stopping possible: APScheduler can unschedule a job but has no notion of
    interrupting the coroutine it already handed to the event loop.
    """

    def __init__(self, jobs: Mapping[str, BatchJob] = BATCH_JOBS) -> None:
        self._jobs = jobs
        self._scheduler = AsyncIOScheduler()
        self._running: dict[UUID, Task[None]] = {}
        # The run each executing row is writing into, so a stop can close it
        # from the request — the one place that is not being cancelled.
        self._runs: dict[UUID, UUID] = {}

    def start(self) -> None:
        self._scheduler.start()

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    def sync(self, batch_id: UUID, code: str, cron: str, *, enabled: bool) -> None:
        """Make the scheduler agree with one batch row.

        The old trigger is removed before the new one is added, rather than
        leaning on `replace_existing` alone: replacement only applies once the
        scheduler is running, so before startup a second sync of the same row
        would queue a second pending job and the schedule would fire twice.

        A run already in flight is left alone: deactivating a schedule says
        "stop starting it", and killing work halfway is a different request.
        """
        self.remove(batch_id)
        if not enabled:
            return
        job = self._job_for(batch_id, code)
        if job is None:
            return
        self._scheduler.add_job(
            self._run,
            CronTrigger.from_crontab(cron),
            kwargs={"batch_id": batch_id, "code": code, "job": job},
            id=str(batch_id),
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
        )

    def remove(self, batch_id: UUID) -> None:
        """Unschedule a row, whether or not it was scheduled."""
        # Deactivating an already-inactive job and deleting a row that was never
        # scheduled both arrive here with the caller's intent already satisfied.
        with suppress(JobLookupError):
            self._scheduler.remove_job(str(batch_id))

    def run_now(self, batch_id: UUID, code: str, actor: str = SCHEDULER_ACTOR) -> None:
        """Fire one execution immediately, outside the row's cron.

        Handed to the same scheduler as a one-shot date job rather than started
        as a loose task: a manual run then executes on the one executor that
        already owns job execution, so `stop` and the run tracking work on it
        exactly as they do on a scheduled run.
        """
        if self.is_running(batch_id):
            raise ConflictError("Batch job is already running", BATCH_ALREADY_RUNNING_CODE)
        job = self._job_for(batch_id, code)
        if job is None:
            raise ConflictError(
                f"No batch job is registered for code '{code}'",
                BATCH_JOB_UNREGISTERED_CODE,
            )
        self._scheduler.add_job(
            self._run,
            DateTrigger(),
            kwargs={
                "batch_id": batch_id,
                "code": code,
                "job": job,
                "trigger": MANUAL_TRIGGER,
                "triggered_by": actor,
            },
            id=f"{batch_id}{MANUAL_RUN_SUFFIX}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
        )

    async def stop(self, batch_id: UUID, actor: str = SCHEDULER_ACTOR) -> bool:
        """Cancel the execution in flight; report whether there was one.

        Idempotent on purpose: "stop" states the wanted end state, and a job
        that finished microseconds before the request is not an error to the
        operator who pressed the button. The schedule is untouched — the next
        cron fire still happens unless the row is deactivated.
        """
        task = self._running.get(batch_id)
        if task is None:
            return False
        # Recorded here, before the cancellation: a write inside the cancelled
        # task is itself cancelled — measured, the row never landed and the
        # stop took seconds. This caller is not being cancelled.
        await self._close_run(self._runs.get(batch_id), "STOPPED", stopped_by=actor)
        task.cancel()
        return True

    def is_running(self, batch_id: UUID) -> bool:
        """Whether an execution of this schedule is in flight **in this process**.

        Public because the list screen shows it: a run button that is live while
        the job is already running, beside a stop button that is live while
        nothing runs, asks the operator to know what the screen would not say.
        The truth is the task map this scheduler cancels from — a `batch_run`
        row still marked RUNNING may belong to a process that is gone.
        """
        return batch_id in self._running

    def _job_for(self, batch_id: UUID, code: str) -> BatchJob | None:
        job = self._jobs.get(code)
        if job is None:
            # A row naming a job this build does not carry — an older or newer
            # deployment wrote it. Skipping one row beats refusing to schedule
            # the others, and the warning names the row to fix.
            logger.warning("batch_job_unknown", batch_id=str(batch_id), code=code)
        return job

    async def _run(
        self,
        batch_id: UUID,
        code: str,
        job: BatchJob,
        trigger: BatchTrigger = CRON_TRIGGER,
        triggered_by: str = SCHEDULER_ACTOR,
    ) -> None:
        """Execute one run and record how it ended.

        The three endings are told apart here because this is the only place
        that can: the job sees its own exception but not a cancellation's
        meaning, and nothing at all sees a killed process — that one is settled
        by the next startup's sweep.
        """
        task = current_task()
        if task is not None:
            self._running[batch_id] = task
        run_id = await self._open_run(batch_id, code, trigger, triggered_by)
        if run_id is not None:
            self._runs[batch_id] = run_id
        token = current_run_id.set(run_id)
        try:
            result = await job()
        except CancelledError:
            # Cancellation is an operator decision, not a failure: it is logged
            # as such and re-raised so the task really ends cancelled.
            # No write here on purpose: this task is the one being cancelled,
            # so the ending was recorded by `stop` before the cancellation.
            logger.warning("batch_job_stopped", batch_id=str(batch_id), code=code)
            raise
        except Exception as exc:
            # A job that raises must not take its own schedule down with it:
            # the next fire is the recovery, and the traceback is the record.
            logger.exception("batch_job_failed", code=code)
            await self._close_run(
                run_id,
                "FAILED",
                error_code=type(exc).__name__,
                error_detail=str(exc),
            )
        else:
            logger.info("batch_job_completed", code=code, result=result)
            await self._close_run(run_id, "SUCCEEDED", result=result)
        finally:
            current_run_id.reset(token)
            self._running.pop(batch_id, None)
            self._runs.pop(batch_id, None)

    async def _open_run(
        self, batch_id: UUID, code: str, trigger: BatchTrigger, triggered_by: str
    ) -> UUID | None:
        """Write the run row before the job's first line, or carry on without it.

        A logging failure must not cost the night's work: the job is the point,
        the row is the record. What is lost then is the record, and the
        exception says so.
        """
        try:
            # expire_on_commit=False, like the request factory: the id is read
            # after the commit, and an expired instance would lazy-load there —
            # which under asyncio is a MissingGreenlet, not a query.
            async with AsyncSession(engine, expire_on_commit=False) as session:
                run = await BatchRunService(session).create_started_run(
                    batch_id, code, trigger, triggered_by
                )
                return run.id
        except Exception:
            logger.exception("batch_run_not_recorded", batch_id=str(batch_id), code=code)
            return None

    async def _close_run(
        self,
        run_id: UUID | None,
        status: BatchRunStatus,
        *,
        result: int | None = None,
        stopped_by: str | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        """Write the ending, if a run was opened at all."""
        if run_id is None:
            return
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await BatchRunService(session).update_finished_run(
                    run_id,
                    status,
                    SCHEDULER_ACTOR,
                    result=result,
                    stopped_by=stopped_by,
                    error_code=error_code,
                    error_detail=error_detail,
                )
        except Exception:
            logger.exception("batch_run_ending_not_recorded", run_id=str(run_id), status=status)


# ============================================================
# Functions
# ============================================================


def validated_cron(cron: str) -> str:
    """Return the expression once APScheduler agrees it is a cron.

    The parser is the authority rather than a regex here: a stored expression
    that this exact `CronTrigger` cannot read is a job that never fires, and
    the request that wrote it is the last moment anyone is watching.
    """
    CronTrigger.from_crontab(cron)
    return cron
