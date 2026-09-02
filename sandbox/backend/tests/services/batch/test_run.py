"""BatchRunService tests — the four endings a run can have, and who says so."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import NotFoundError
from app.dependencies.services import get_batch_run_service
from app.models.batch.schedule import BatchSchedule
from app.schemas.batch.run import BatchRunUpdateRequest, to_read, to_read_list
from app.services.batch.run import BatchRunService


CODE = "sync_barcode_ledger"


@pytest.mark.asyncio
async def test_create_started_run_opens_a_running_row(factory) -> None:
    """A run is written before the job's first line, not after its last.

    A process that dies immediately must still leave the fact that it started;
    a row written at the end would make a crashed run indistinguishable from
    one that never fired.
    """
    async with factory() as session:
        run = await BatchRunService(session).create_started_run(None, CODE, "CRON", "scheduler")

    assert run.status == "RUNNING"
    assert run.finished_at is None
    assert run.triggered_by == "scheduler"
    assert run.code == CODE


@pytest.mark.asyncio
async def test_list_schedule_runs_is_scoped_and_newest_first(factory) -> None:
    """The history dialog reads one schedule's runs.

    Another schedule's runs and an orphaned run (batch_id NULL after the
    schedule's deletion) must not appear, and the newest run comes first.
    """
    async with factory() as session:
        mine_row = BatchSchedule(code=CODE, name="mine", cron="0 2 * * *", created_by="t")
        other_row = BatchSchedule(code=CODE, name="other", cron="0 3 * * *", created_by="t")
        session.add(mine_row)
        session.add(other_row)
        await session.commit()
        mine, other = mine_row.id, other_row.id

    async with factory() as session:
        service = BatchRunService(session)
        first = await service.create_started_run(mine, CODE, "CRON", "scheduler")
        second = await service.create_started_run(mine, CODE, "MANUAL", "tester")
        await service.create_started_run(other, CODE, "CRON", "scheduler")
        await service.create_started_run(None, CODE, "MANUAL", "cli")

        runs = await service.list_schedule_runs(mine)

    assert [run.id for run in runs] == [second.id, first.id]


@pytest.mark.asyncio
async def test_update_finished_run_measures_from_the_stored_start(factory) -> None:
    """Duration comes from the row, not from the caller that reports the ending.

    The scheduler that closes a run is not always the code that opened it;
    two clocks would drift and the log would keep a duration nobody measured.
    """
    async with factory() as session:
        run = await BatchRunService(session).create_started_run(None, CODE, "CRON", "scheduler")

    async with factory() as session:
        finished = await BatchRunService(session).update_finished_run(
            run.id, "SUCCEEDED", "scheduler", result=1891
        )

    assert finished.status == "SUCCEEDED"
    assert finished.finished_at is not None
    assert finished.duration_ms is not None and finished.duration_ms >= 0
    assert finished.result == 1891


@pytest.mark.asyncio
async def test_stopped_run_records_who_stopped_it(factory) -> None:
    """A stop is an operator's decision, so the log names the operator.

    Without the name, a stopped nightly run and a crashed one read the same in
    the morning.
    """
    async with factory() as session:
        run = await BatchRunService(session).create_started_run(None, CODE, "MANUAL", "tester")

    async with factory() as session:
        stopped = await BatchRunService(session).update_finished_run(
            run.id, "STOPPED", "tester", stopped_by="tester"
        )

    assert (stopped.status, stopped.stopped_by) == ("STOPPED", "tester")


@pytest.mark.asyncio
async def test_update_interrupted_runs_settles_only_unfinished_rows(factory) -> None:
    """A killed process leaves no writer, so the next startup speaks for it.

    Only `RUNNING` rows are swept: a finished run rewritten as interrupted
    would erase the ending it actually had.
    """
    async with factory() as session:
        orphan = await BatchRunService(session).create_started_run(None, CODE, "CRON", "scheduler")

    async with factory() as session:
        done = await BatchRunService(session).create_started_run(None, CODE, "CRON", "scheduler")

    async with factory() as session:
        await BatchRunService(session).update_finished_run(done.id, "SUCCEEDED", "scheduler")

    async with factory() as session:
        assert await BatchRunService(session).update_interrupted_runs("scheduler") == 1

    async with factory() as session:
        batch_run_service = BatchRunService(session)
        assert (await batch_run_service.get_run(orphan.id)).status == "INTERRUPTED"
        assert (await batch_run_service.get_run(done.id)).status == "SUCCEEDED"

    async with factory() as session:
        assert await BatchRunService(session).update_interrupted_runs("scheduler") == 0


@pytest.mark.asyncio
async def test_a_finished_run_must_carry_a_finishing_time(factory) -> None:
    """The database holds the state machine, not just the writers.

    `RUNNING` with a finish time — or an ending without one — is a row no
    reader can interpret, so the CHECK refuses it however it was produced.
    """
    async with factory() as session:
        run = await BatchRunService(session).create_started_run(None, CODE, "CRON", "scheduler")

    with pytest.raises(IntegrityError):
        async with factory() as session:
            await BatchRunService(session).update_run(
                run.id, BatchRunUpdateRequest(status="SUCCEEDED"), updated_by="scheduler"
            )


@pytest.mark.asyncio
async def test_run_crud_and_missing_rows(factory) -> None:
    """The plain verbs, and the 404 each one owes for an id the table lacks."""
    missing = uuid4()
    async with factory() as session:
        created = await BatchRunService(session).create_started_run(None, CODE, "CRON", "scheduler")

    async with factory() as session:
        batch_run_service = BatchRunService(session)
        assert (await batch_run_service.get_run(created.id)).code == CODE
        assert len(await batch_run_service.list_runs()) == 1

    read = to_read(created)
    assert read.status == "RUNNING"
    assert read.version == 1
    assert [row.id for row in to_read_list([created])] == [created.id]

    async with factory() as session:
        await BatchRunService(session).delete_run(created.id)

    async with factory() as session:
        batch_run_service = BatchRunService(session)
        with pytest.raises(NotFoundError):
            await batch_run_service.get_run(missing)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchRunService(session).update_run(
                missing, BatchRunUpdateRequest(result=1), updated_by="scheduler"
            )

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchRunService(session).delete_run(missing)


@pytest.mark.asyncio
async def test_update_run_writes_a_correction_and_refuses_a_missing_row(factory) -> None:
    """The plain update exists for corrections, and owes a 404 like every verb.

    `update_finished_run` is the state machine; this is the raw write beneath
    it, and an operator fixing a mislabelled run goes through here.
    """
    async with factory() as session:
        run = await BatchRunService(session).create_started_run(None, CODE, "CRON", "scheduler")

    async with factory() as session:
        corrected = await BatchRunService(session).update_run(
            run.id, BatchRunUpdateRequest(result=7), updated_by="tester"
        )
        assert (corrected.result, corrected.status) == (7, "RUNNING")

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchRunService(session).update_finished_run(uuid4(), "SUCCEEDED", "scheduler")


@pytest.mark.asyncio
async def test_find_finished_before_reads_the_ending_not_the_birth(factory) -> None:
    """Retention asks when a run ended — a RUNNING row has no age at all.

    A `created_at` cutoff would purge a long initial load while it is still
    walking its windows; `finished_at` cannot, because the row has none.
    """
    async with factory() as session:
        open_run = await BatchRunService(session).create_started_run(
            None, CODE, "CRON", "scheduler"
        )

    async with factory() as session:
        done = await BatchRunService(session).create_started_run(None, CODE, "CRON", "scheduler")

    async with factory() as session:
        await BatchRunService(session).update_finished_run(done.id, "SUCCEEDED", "scheduler")

    async with factory() as session:
        batch_run_service = BatchRunService(session)
        old = await batch_run_service.find_finished_before(datetime.now(UTC) + timedelta(days=1))
        assert [run.id for run in old] == [done.id]
        assert open_run.id not in {run.id for run in old}
        earlier = await batch_run_service.find_finished_before(
            datetime.now(UTC) - timedelta(days=1)
        )
        assert earlier == []


@pytest.mark.asyncio
async def test_an_ending_is_written_once(factory) -> None:
    """A stop recorded from the request and a job that finished anyway collide.

    Both write an ending for the same run; the first one wins, because a log
    that kept the later writer would report a stopped run as successful.
    """
    async with factory() as session:
        run = await BatchRunService(session).create_started_run(None, CODE, "MANUAL", "tester")

    async with factory() as session:
        await BatchRunService(session).update_finished_run(
            run.id, "STOPPED", "tester", stopped_by="operator"
        )

    async with factory() as session:
        again = await BatchRunService(session).update_finished_run(
            run.id, "SUCCEEDED", "scheduler", result=7
        )

    assert (again.status, again.stopped_by, again.result) == ("STOPPED", "operator", None)


@pytest.mark.asyncio
async def test_get_batch_run_service_binds_the_request_session(factory) -> None:
    """The DI factory hands an endpoint a service on the request's own session."""
    async with factory() as session:
        batch_run_service = get_batch_run_service(session)
        assert isinstance(batch_run_service, BatchRunService)
        assert batch_run_service.session is session


@pytest.mark.asyncio
async def test_count_schedule_runs_counts_one_schedule_only(factory) -> None:
    """The total carries the same filter as the page it describes.

    Another schedule's runs and the orphaned rows (`batch_id` NULL) share the
    table, so a count without the predicate would report a number no page of
    this schedule can reach.
    """
    async with factory() as session:
        mine_row = BatchSchedule(code=CODE, name="mine", cron="0 2 * * *", created_by="t")
        session.add(mine_row)
        await session.commit()
        mine = mine_row.id

    async with factory() as session:
        service = BatchRunService(session)
        for _ in range(3):
            await service.create_started_run(mine, CODE, "CRON", "scheduler")
        await service.create_started_run(None, CODE, "MANUAL", "cli")

        page = await service.list_schedule_runs(mine, offset=2, limit=1)
        total = await service.count_schedule_runs(mine)

    assert len(page) == 1
    assert total == 3
