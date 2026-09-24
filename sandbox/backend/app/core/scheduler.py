# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from asyncio import CancelledError, Lock, Task, current_task
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from types import MappingProxyType
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from app.batch.derive_food_tables import derive_food_tables
from app.batch.purge_expired_refreshes import purge_expired_refreshes
from app.batch.purge_old_batch_runs import purge_old_batch_runs
from app.batch.sync_food_ledger_additive_manufacturing_closure import (
    sync_food_ledger_additive_manufacturing_closure,
)
from app.batch.sync_food_ledger_admin_disposition import sync_food_ledger_admin_disposition
from app.batch.sync_food_ledger_barcode import sync_food_ledger_barcode
from app.batch.sync_food_ledger_business import sync_food_ledger_business
from app.batch.sync_food_ledger_business_site import sync_food_ledger_business_site
from app.batch.sync_food_ledger_collection_inspection import (
    sync_food_ledger_collection_inspection,
)
from app.batch.sync_food_ledger_common_standard import sync_food_ledger_common_standard
from app.batch.sync_food_ledger_common_standard_exclusion import (
    sync_food_ledger_common_standard_exclusion,
)
from app.batch.sync_food_ledger_common_standard_type import sync_food_ledger_common_standard_type
from app.batch.sync_food_ledger_haccp_label import sync_food_ledger_haccp_label
from app.batch.sync_food_ledger_health_functional_closure import (
    sync_food_ledger_health_functional_closure,
)
from app.batch.sync_food_ledger_health_functional_item_report import (
    sync_food_ledger_health_functional_item_report,
)
from app.batch.sync_food_ledger_health_functional_production import (
    sync_food_ledger_health_functional_production,
)
from app.batch.sync_food_ledger_import_business_closure import (
    sync_food_ledger_import_business_closure,
)
from app.batch.sync_food_ledger_import_food_label import sync_food_ledger_import_food_label
from app.batch.sync_food_ledger_individual_standard import sync_food_ledger_individual_standard
from app.batch.sync_food_ledger_inspection_failure import sync_food_ledger_inspection_failure
from app.batch.sync_food_ledger_item_report import sync_food_ledger_item_report
from app.batch.sync_food_ledger_item_report_raw_material import (
    sync_food_ledger_item_report_raw_material,
)
from app.batch.sync_food_ledger_livestock_item_report_raw_material import (
    sync_food_ledger_livestock_item_report_raw_material,
)
from app.batch.sync_food_ledger_livestock_processing_closure import (
    sync_food_ledger_livestock_processing_closure,
)
from app.batch.sync_food_ledger_livestock_production import sync_food_ledger_livestock_production
from app.batch.sync_food_ledger_manufacturing_closure import sync_food_ledger_manufacturing_closure
from app.batch.sync_food_ledger_meat_packaging_closure import (
    sync_food_ledger_meat_packaging_closure,
)
from app.batch.sync_food_ledger_nutrition import sync_food_ledger_nutrition
from app.batch.sync_food_ledger_product_classification import (
    sync_food_ledger_product_classification,
)
from app.batch.sync_food_ledger_production import sync_food_ledger_production
from app.batch.sync_food_ledger_qr_allergy import sync_food_ledger_qr_allergy
from app.batch.sync_food_ledger_qr_caution import sync_food_ledger_qr_caution
from app.batch.sync_food_ledger_qr_label import sync_food_ledger_qr_label
from app.batch.sync_food_ledger_qr_manufacture import sync_food_ledger_qr_manufacture
from app.batch.sync_food_ledger_qr_nutrition import sync_food_ledger_qr_nutrition
from app.batch.sync_food_ledger_qr_packaging import sync_food_ledger_qr_packaging
from app.batch.sync_food_ledger_qr_raw_material import sync_food_ledger_qr_raw_material
from app.batch.sync_food_ledger_qr_storage import sync_food_ledger_qr_storage
from app.batch.sync_food_ledger_raw_material import sync_food_ledger_raw_material
from app.batch.sync_food_ledger_recall import sync_food_ledger_recall
from app.batch.sync_food_ledger_test_item import sync_food_ledger_test_item
from app.core.database import engine
from app.core.exceptions import BatchSkippedError, ConflictError
from app.core.settings import settings
from app.schemas.batch.run import (
    ERROR_CODE_MAX_LENGTH,
    ERROR_DETAIL_MAX_LENGTH,
    BatchRunStatus,
    BatchTrigger,
)
from app.services.batch.run import BatchRunService, current_run_id, run_start_gate


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
        "derive_food_tables": derive_food_tables,
        "purge_expired_refreshes": purge_expired_refreshes,
        "purge_old_batch_runs": purge_old_batch_runs,
        "sync_food_ledger_barcode": sync_food_ledger_barcode,
        "sync_food_ledger_additive_manufacturing_closure": (
            sync_food_ledger_additive_manufacturing_closure
        ),
        "sync_food_ledger_business": sync_food_ledger_business,
        "sync_food_ledger_business_site": sync_food_ledger_business_site,
        "sync_food_ledger_collection_inspection": sync_food_ledger_collection_inspection,
        "sync_food_ledger_common_standard": sync_food_ledger_common_standard,
        "sync_food_ledger_common_standard_exclusion": sync_food_ledger_common_standard_exclusion,
        "sync_food_ledger_common_standard_type": sync_food_ledger_common_standard_type,
        "sync_food_ledger_haccp_label": sync_food_ledger_haccp_label,
        "sync_food_ledger_health_functional_closure": sync_food_ledger_health_functional_closure,
        "sync_food_ledger_health_functional_item_report": (
            sync_food_ledger_health_functional_item_report
        ),
        "sync_food_ledger_health_functional_production": (
            sync_food_ledger_health_functional_production
        ),
        "sync_food_ledger_import_food_label": sync_food_ledger_import_food_label,
        "sync_food_ledger_import_business_closure": sync_food_ledger_import_business_closure,
        "sync_food_ledger_individual_standard": sync_food_ledger_individual_standard,
        "sync_food_ledger_admin_disposition": sync_food_ledger_admin_disposition,
        "sync_food_ledger_inspection_failure": sync_food_ledger_inspection_failure,
        "sync_food_ledger_item_report": sync_food_ledger_item_report,
        "sync_food_ledger_item_report_raw_material": sync_food_ledger_item_report_raw_material,
        "sync_food_ledger_livestock_item_report_raw_material": (
            sync_food_ledger_livestock_item_report_raw_material
        ),
        "sync_food_ledger_livestock_production": sync_food_ledger_livestock_production,
        "sync_food_ledger_livestock_processing_closure": (
            sync_food_ledger_livestock_processing_closure
        ),
        "sync_food_ledger_manufacturing_closure": sync_food_ledger_manufacturing_closure,
        "sync_food_ledger_meat_packaging_closure": sync_food_ledger_meat_packaging_closure,
        "sync_food_ledger_nutrition": sync_food_ledger_nutrition,
        "sync_food_ledger_product_classification": sync_food_ledger_product_classification,
        "sync_food_ledger_production": sync_food_ledger_production,
        "sync_food_ledger_qr_allergy": sync_food_ledger_qr_allergy,
        "sync_food_ledger_qr_caution": sync_food_ledger_qr_caution,
        "sync_food_ledger_qr_label": sync_food_ledger_qr_label,
        "sync_food_ledger_qr_manufacture": sync_food_ledger_qr_manufacture,
        "sync_food_ledger_qr_nutrition": sync_food_ledger_qr_nutrition,
        "sync_food_ledger_qr_packaging": sync_food_ledger_qr_packaging,
        "sync_food_ledger_qr_raw_material": sync_food_ledger_qr_raw_material,
        "sync_food_ledger_qr_storage": sync_food_ledger_qr_storage,
        "sync_food_ledger_raw_material": sync_food_ledger_raw_material,
        "sync_food_ledger_recall": sync_food_ledger_recall,
        "sync_food_ledger_test_item": sync_food_ledger_test_item,
    }
)

# Which provider a job's walk queues behind. Two jobs of one provider share a
# host, a key pool and whatever that portal limits; running them at once buys
# nothing and spends the same quota, so the scheduler lets one through at a
# time. Two providers share nothing and overlap freely. A code missing here -
# the purges, the derive job - waits for nobody.
JOB_PROVIDERS: Mapping[str, str] = MappingProxyType(
    {
        "sync_food_ledger_barcode": "mfds-food-safety-korea",
        "sync_food_ledger_business": "mfds-food-safety-korea",
        "sync_food_ledger_business_site": "mfds-food-safety-korea",
        "sync_food_ledger_manufacturing_closure": "mfds-food-safety-korea",
        "sync_food_ledger_additive_manufacturing_closure": "mfds-food-safety-korea",
        "sync_food_ledger_import_business_closure": "mfds-food-safety-korea",
        "sync_food_ledger_health_functional_closure": "mfds-food-safety-korea",
        "sync_food_ledger_livestock_processing_closure": "mfds-food-safety-korea",
        "sync_food_ledger_meat_packaging_closure": "mfds-food-safety-korea",
        "sync_food_ledger_collection_inspection": "mfds-food-safety-korea",
        "sync_food_ledger_common_standard": "mfds-food-safety-korea",
        "sync_food_ledger_common_standard_exclusion": "mfds-food-safety-korea",
        "sync_food_ledger_common_standard_type": "mfds-food-safety-korea",
        "sync_food_ledger_haccp_label": "data-go-kr",
        "sync_food_ledger_health_functional_item_report": "mfds-food-safety-korea",
        "sync_food_ledger_health_functional_production": "mfds-food-safety-korea",
        "sync_food_ledger_import_food_label": "data-go-kr",
        "sync_food_ledger_individual_standard": "mfds-food-safety-korea",
        "sync_food_ledger_admin_disposition": "mfds-food-safety-korea",
        "sync_food_ledger_inspection_failure": "mfds-food-safety-korea",
        "sync_food_ledger_item_report": "mfds-food-safety-korea",
        "sync_food_ledger_item_report_raw_material": "mfds-food-safety-korea",
        "sync_food_ledger_livestock_item_report_raw_material": "mfds-food-safety-korea",
        "sync_food_ledger_livestock_production": "mfds-food-safety-korea",
        "sync_food_ledger_nutrition": "data-go-kr",
        "sync_food_ledger_product_classification": "mfds-food-safety-korea",
        "sync_food_ledger_production": "mfds-food-safety-korea",
        "sync_food_ledger_qr_allergy": "data-go-kr",
        "sync_food_ledger_qr_caution": "data-go-kr",
        "sync_food_ledger_qr_label": "data-go-kr",
        "sync_food_ledger_qr_manufacture": "data-go-kr",
        "sync_food_ledger_qr_nutrition": "data-go-kr",
        "sync_food_ledger_qr_packaging": "data-go-kr",
        "sync_food_ledger_qr_raw_material": "data-go-kr",
        "sync_food_ledger_qr_storage": "data-go-kr",
        "sync_food_ledger_raw_material": "mfds-food-safety-korea",
        "sync_food_ledger_recall": "mfds-food-safety-korea",
        "sync_food_ledger_test_item": "mfds-food-safety-korea",
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

    def __init__(
        self,
        jobs: Mapping[str, BatchJob] = BATCH_JOBS,
        providers: Mapping[str, str] = JOB_PROVIDERS,
    ) -> None:
        self._jobs = jobs
        self._providers = providers
        # One lock per provider, made on first use: the jobs of one provider
        # take turns, and a job whose code names none takes nobody's.
        self._provider_locks: dict[str, Lock] = {}
        # The zone every cron row is read against, stated rather than inherited:
        # an APScheduler with no timezone takes the process's, which in a
        # container is UTC, and each row would then mean nine hours from what
        # its author wrote (settings.scheduler_timezone).
        self._scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.scheduler_timezone))
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
            # The zone belongs on the trigger, not only on the scheduler: a
            # trigger handed in ready-made keeps whatever zone it was built
            # with, and `from_crontab` builds with the *process's* — measured,
            # a row read as Seoul on a laptop and as UTC in the container.
            CronTrigger.from_crontab(cron, timezone=ZoneInfo(settings.scheduler_timezone)),
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

        Not while another execution of the row is in flight: APScheduler's
        `max_instances` only knows a job id, and a manual run carries a
        different one (`MANUAL_RUN_SUFFIX`), so a cron fire during a manual
        run — or the reverse — would have two runs writing over the same
        ledgers at once. Checked here rather than only in `run_now`, because
        this is the one entry every execution passes; the skip is a log line,
        as APScheduler's own skip of a cron fire during a cron run is
        (observed 2026-09-08 00:00, the 22:38 run still walking).

        The three endings are told apart here because this is the only place
        that can: the job sees its own exception but not a cancellation's
        meaning, and nothing at all sees a killed process — that one is settled
        by the next startup's sweep.
        """
        if self.is_running(batch_id):
            logger.warning(
                "batch_job_overlapped", batch_id=str(batch_id), code=code, trigger=trigger
            )
            return
        task = current_task()
        if task is not None:
            self._running[batch_id] = task
        # The job's task is a copy of whichever context last woke the
        # scheduler, a request's included: measured 2026-09-08, a night's
        # 3,505 provider calls carried the `request_id` of the PATCH that had
        # edited a cron hours before. Cleared here, so the run's log lines and
        # call rows name the run and nothing else.
        structlog.contextvars.clear_contextvars()
        run_id = await self._open_run(batch_id, code, trigger, triggered_by)
        structlog.contextvars.bind_contextvars(
            batch_id=str(batch_id), code=code, run_id=str(run_id), trigger=trigger
        )
        if run_id is not None:
            self._runs[batch_id] = run_id
        token = current_run_id.set(run_id)
        provider = self._providers.get(code)
        lock = self._provider_locks.setdefault(provider, Lock()) if provider else None
        try:
            if lock is None:
                result = await job()
            else:
                # Held across the whole walk: the portal is the resource, and a
                # second walk of it would spend the same quota to go slower. A
                # job waiting here is RUNNING with no calls yet, which is what
                # the derive job's dependency check wants to see.
                async with lock:
                    result = await job()
        except CancelledError:
            # Cancellation is an operator decision, not a failure: it is logged
            # as such and re-raised so the task really ends cancelled.
            # No write here on purpose: this task is the one being cancelled,
            # so the ending was recorded by `stop` before the cancellation.
            logger.warning("batch_job_stopped", batch_id=str(batch_id), code=code)
            raise
        except BatchSkippedError as exc:
            # The job decided this fire has nothing to do. An ending of its
            # own, so a reader of the log can tell a quiet day from a broken
            # one without opening the job's source.
            logger.info("batch_job_skipped", code=code, reason=exc.reason)
            await self._close_run(run_id, "SKIPPED", error_detail=exc.reason)
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
            # Under the start gate: a job that decides whether to run by
            # reading the running rows must not read them while this row is
            # half-written, or two jobs each find the table empty.
            # expire_on_commit=False, like the request factory: the id is read
            # after the commit, and an expired instance would lazy-load there —
            # which under asyncio is a MissingGreenlet, not a query.
            async with run_start_gate(), AsyncSession(engine, expire_on_commit=False) as session:
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
        """Write the ending, if a run was opened at all.

        The ending is cut to what the row can hold before it is written. A
        driver's message is as long as it likes (asyncpg prints the offending
        value), and an ending refused for its own length would leave the run
        RUNNING for ever - which is worse than a clipped message, because a
        run that never ends is a run no schedule will fire again.
        """
        if run_id is None:
            return
        error_code = None if error_code is None else error_code[:ERROR_CODE_MAX_LENGTH]
        error_detail = None if error_detail is None else error_detail[:ERROR_DETAIL_MAX_LENGTH]
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
