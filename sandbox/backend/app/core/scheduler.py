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

from app.batch.refreshes import purge_expired_refreshes
from app.core.exceptions import ConflictError


# ============================================================
# Constants
# ============================================================

type BatchJob = Callable[[], Awaitable[int]]

# The only place a job code becomes runnable Python. A `batch` row names a key
# here, so adding a job is one function plus one row — the lifespan never grows
# a branch, and a code nothing implements is rejected at the API boundary
# instead of failing silently at 03:00.
BATCH_JOBS: Mapping[str, BatchJob] = MappingProxyType(
    {
        "purge_expired_refreshes": purge_expired_refreshes,
    }
)

# A restart across the scheduled minute must still run the job. One hour is the
# window in which a late run is worth more than a skipped one.
MISFIRE_GRACE_SECONDS = 3600

# A manual run carries its own scheduler id so it cannot evict the row's cron
# job — the two are different things and must be able to coexist.
MANUAL_RUN_SUFFIX = ":run-now"

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

    def run_now(self, batch_id: UUID, code: str) -> None:
        """Fire one execution immediately, outside the row's cron.

        Handed to the same scheduler as a one-shot date job rather than started
        as a loose task: a manual run then executes on the one executor that
        already owns job execution, so `stop` and the run tracking work on it
        exactly as they do on a scheduled run.
        """
        if self.is_running(batch_id):
            raise ConflictError("Batch job is already running")
        job = self._job_for(batch_id, code)
        if job is None:
            raise ConflictError(f"No batch job is registered for code '{code}'")
        self._scheduler.add_job(
            self._run,
            DateTrigger(),
            kwargs={"batch_id": batch_id, "code": code, "job": job},
            id=f"{batch_id}{MANUAL_RUN_SUFFIX}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
        )

    def stop(self, batch_id: UUID) -> bool:
        """Cancel the execution in flight; report whether there was one.

        Idempotent on purpose: "stop" states the wanted end state, and a job
        that finished microseconds before the request is not an error to the
        operator who pressed the button. The schedule is untouched — the next
        cron fire still happens unless the row is deactivated.
        """
        task = self._running.get(batch_id)
        if task is None:
            return False
        task.cancel()
        return True

    def is_running(self, batch_id: UUID) -> bool:
        return batch_id in self._running

    def _job_for(self, batch_id: UUID, code: str) -> BatchJob | None:
        job = self._jobs.get(code)
        if job is None:
            # A row naming a job this build does not carry — an older or newer
            # deployment wrote it. Skipping one row beats refusing to schedule
            # the others, and the warning names the row to fix.
            logger.warning("batch_job_unknown", batch_id=str(batch_id), code=code)
        return job

    async def _run(self, batch_id: UUID, code: str, job: BatchJob) -> None:
        task = current_task()
        if task is not None:
            self._running[batch_id] = task
        try:
            result = await job()
        except CancelledError:
            # Cancellation is an operator decision, not a failure: it is logged
            # as such and re-raised so the task really ends cancelled.
            logger.warning("batch_job_stopped", batch_id=str(batch_id), code=code)
            raise
        except Exception:
            # A job that raises must not take its own schedule down with it:
            # the next fire is the recovery, and the traceback is the record.
            logger.exception("batch_job_failed", code=code)
        else:
            logger.info("batch_job_completed", code=code, result=result)
        finally:
            self._running.pop(batch_id, None)


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
