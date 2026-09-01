"""BatchScheduler tests — the running schedule follows the row, or it is not a schedule."""

import asyncio
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError
from app.core.scheduler import BATCH_JOBS, BatchScheduler, validated_cron


CRON = "0 3 * * *"

JOB_CODE = "test_job"

POLL_SECONDS = 0.01


async def _until(condition, timeout: float = 2.0) -> None:
    """Wait for the scheduler's own loop to reach a state, or fail the test.

    The executor runs jobs as tasks, so nothing here is synchronous with the
    call that scheduled them — polling the state is what a caller can observe.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition():
        assert asyncio.get_running_loop().time() < deadline, "timed out waiting for the scheduler"
        await asyncio.sleep(POLL_SECONDS)


def _blocking_scheduler(release: asyncio.Event) -> BatchScheduler:
    """A scheduler whose job waits, so a run can be observed while in flight."""

    async def _job() -> int:
        await release.wait()
        return 0

    return BatchScheduler(jobs={JOB_CODE: _job})


def _scheduler(calls: list[int] | None = None) -> BatchScheduler:
    """A scheduler carrying one recording job, so a fired run is observable."""

    async def _job() -> int:
        if calls is not None:
            calls.append(1)
        return 7

    return BatchScheduler(jobs={JOB_CODE: _job})


def test_sync_schedules_an_enabled_row() -> None:
    """The row id is the job id — that is what lets a later edit replace it."""
    scheduler = _scheduler()
    batch_id = uuid4()

    scheduler.sync(batch_id, JOB_CODE, CRON, enabled=True)

    assert [job.id for job in scheduler._scheduler.get_jobs()] == [str(batch_id)]


@pytest.mark.asyncio
async def test_sync_replaces_the_previous_trigger() -> None:
    """A cron edit must not leave the old trigger running beside the new one.

    Against a *started* scheduler, because that is where `replace_existing`
    acts — a stopped one only queues pending jobs and would hide the duplicate.
    """
    scheduler = _scheduler()
    batch_id = uuid4()
    scheduler.start()

    scheduler.sync(batch_id, JOB_CODE, CRON, enabled=True)
    scheduler.sync(batch_id, JOB_CODE, "30 4 * * *", enabled=True)

    jobs = scheduler._scheduler.get_jobs()
    scheduler.shutdown()
    assert len(jobs) == 1
    assert "hour='4'" in str(jobs[0].trigger)


def test_sync_disabled_stops_the_job() -> None:
    """`enabled = false` is the stop switch: the trigger has to be gone."""
    scheduler = _scheduler()
    batch_id = uuid4()

    scheduler.sync(batch_id, JOB_CODE, CRON, enabled=True)
    scheduler.sync(batch_id, JOB_CODE, CRON, enabled=False)

    assert scheduler._scheduler.get_jobs() == []


def test_sync_skips_a_code_this_build_cannot_run() -> None:
    """A row from another deployment is skipped, not fatal — the rest still schedule."""
    scheduler = _scheduler()
    unknown_id = uuid4()
    known_id = uuid4()

    scheduler.sync(unknown_id, "job_from_the_future", CRON, enabled=True)
    scheduler.sync(known_id, JOB_CODE, CRON, enabled=True)

    assert [job.id for job in scheduler._scheduler.get_jobs()] == [str(known_id)]


def test_remove_is_silent_when_nothing_is_scheduled() -> None:
    """Deleting a row that was never scheduled must not fail the request."""
    _scheduler().remove(uuid4())


@pytest.mark.asyncio
async def test_run_executes_the_registered_job() -> None:
    """The scheduler's only job is to call the code the row names."""
    calls: list[int] = []
    scheduler = _scheduler(calls)

    await scheduler._run(uuid4(), JOB_CODE, scheduler._jobs[JOB_CODE])

    assert calls == [1]


@pytest.mark.asyncio
async def test_run_survives_a_failing_job() -> None:
    """A raising job must not take its own schedule down: the next fire is the retry."""

    async def _boom() -> int:
        raise RuntimeError("provider down")

    scheduler = BatchScheduler(jobs={JOB_CODE: _boom})

    await scheduler._run(uuid4(), JOB_CODE, _boom)


@pytest.mark.asyncio
async def test_run_now_executes_outside_the_schedule() -> None:
    """The manual run is the whole point of the button: no cron, one execution."""
    calls: list[int] = []
    scheduler = _scheduler(calls)
    scheduler.start()

    scheduler.run_now(uuid4(), JOB_CODE)
    await _until(lambda: calls == [1])

    scheduler.shutdown()


@pytest.mark.asyncio
async def test_run_now_refuses_a_second_concurrent_run() -> None:
    """Two runs of one job at once would act on the same rows twice."""
    release = asyncio.Event()
    scheduler = _blocking_scheduler(release)
    batch_id = uuid4()
    scheduler.start()

    scheduler.run_now(batch_id, JOB_CODE)
    await _until(lambda: scheduler.is_running(batch_id))

    with pytest.raises(ConflictError):
        scheduler.run_now(batch_id, JOB_CODE)

    release.set()
    await _until(lambda: not scheduler.is_running(batch_id))
    scheduler.shutdown()


@pytest.mark.asyncio
async def test_stop_cancels_the_execution_in_flight() -> None:
    """Stopping is cancelling the coroutine — unscheduling would leave it running."""
    release = asyncio.Event()
    scheduler = _blocking_scheduler(release)
    batch_id = uuid4()
    scheduler.start()

    scheduler.run_now(batch_id, JOB_CODE)
    await _until(lambda: scheduler.is_running(batch_id))

    assert scheduler.stop(batch_id) is True
    await _until(lambda: not scheduler.is_running(batch_id))
    assert not release.is_set()

    scheduler.shutdown()


@pytest.mark.asyncio
async def test_stop_is_idempotent_when_nothing_runs() -> None:
    """A job that finished a moment ago is not an error to the operator who stopped it."""
    assert _scheduler().stop(uuid4()) is False


@pytest.mark.asyncio
async def test_run_now_rejects_a_code_this_build_cannot_run() -> None:
    """A manual run of an unknown code must say so, not fail silently at the executor."""
    with pytest.raises(ConflictError):
        _scheduler().run_now(uuid4(), "job_from_the_future")


@pytest.mark.asyncio
async def test_start_and_shutdown() -> None:
    """The lifespan's two calls, exercised against a real event loop.

    The sleep is not padding: AsyncIOScheduler defers its shutdown onto the
    loop, so the state only settles on the next iteration.
    """
    scheduler = _scheduler()

    scheduler.start()
    assert scheduler._scheduler.running
    scheduler.shutdown()
    await asyncio.sleep(0)

    assert not scheduler._scheduler.running


def test_validated_cron_accepts_a_crontab_expression() -> None:
    """The value is returned unchanged — validation must not rewrite the row."""
    assert validated_cron(CRON) == CRON


def test_validated_cron_rejects_a_broken_expression() -> None:
    """A cron the trigger cannot parse is a job that would never fire."""
    with pytest.raises(ValueError, match="Wrong number of fields"):
        validated_cron("every tuesday")


def test_shipped_registry_is_runnable() -> None:
    """Every registered code maps to a callable — the API offers exactly these."""
    assert all(callable(job) for job in BATCH_JOBS.values())
