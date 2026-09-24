"""BatchStepService tests — one row per finished unit, and what it may claim."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import NotFoundError
from app.dependencies.services import get_batch_step_service
from app.schemas.batch.step import BatchStepUpdateRequest, to_read, to_read_list
from app.services.batch.run import BatchRunService
from app.services.batch.step import BatchStepService


CODE = "sync_mfds_ledgers"

ACTOR = "batch:sync_mfds_ledgers"


async def _run_id(factory) -> UUID:
    """A step needs a run: `run_id` is a NOT NULL foreign key."""
    async with factory() as session:
        run = await BatchRunService(session).create_started_run(None, CODE, "CRON", "scheduler")
    return run.id


@pytest.mark.asyncio
async def test_create_finished_step_derives_its_status_from_the_error(factory) -> None:
    """A step that reports an error is a failed step — the caller cannot say otherwise.

    Passing the status separately lets one call claim both things at once, and
    the log would keep whichever the writer happened to pass.
    """
    run_id = await _run_id(factory)
    async with factory() as session:
        ok = await BatchStepService(session).create_finished_step(
            run_id, 1, 2704, ACTOR, range_start=1, range_end=1000, received=1000, written=976
        )

    async with factory() as session:
        bad = await BatchStepService(session).create_finished_step(
            run_id,
            2,
            235,
            ACTOR,
            range_start=1001,
            range_end=2000,
            error_code="integration_error",
            error_detail="External API refused the request: result_code=ERROR-336",
        )

    assert (ok.status, ok.written) == ("SUCCEEDED", 976)
    assert (bad.status, bad.written) == ("FAILED", None)
    assert bad.error_code == "integration_error"


@pytest.mark.asyncio
async def test_steps_of_one_run_come_back_in_order(factory) -> None:
    """A run's story is the sequence; unordered rows make the last window unfindable."""
    run_id = await _run_id(factory)
    for sequence in (2, 1, 3):
        async with factory() as session:
            await BatchStepService(session).create_finished_step(run_id, sequence, 10, ACTOR)

    async with factory() as session:
        steps = await BatchStepService(session).list_run_steps(run_id)

    assert [step.sequence for step in steps] == [1, 2, 3]


@pytest.mark.asyncio
async def test_a_run_cannot_hold_the_same_sequence_twice(factory) -> None:
    """Two rows for page 3 would double every count read off this table.

    A retry writes a new run, not a second row for the same window.
    """
    run_id = await _run_id(factory)
    async with factory() as session:
        await BatchStepService(session).create_finished_step(run_id, 1, 10, ACTOR)

    with pytest.raises(IntegrityError):
        async with factory() as session:
            await BatchStepService(session).create_finished_step(run_id, 1, 10, ACTOR)


@pytest.mark.asyncio
async def test_step_crud_and_missing_rows(factory) -> None:
    """The plain verbs, and the 404 each one owes for an id the table lacks."""
    run_id = await _run_id(factory)
    missing = uuid4()
    async with factory() as session:
        created = await BatchStepService(session).create_finished_step(run_id, 1, 5, ACTOR)

    async with factory() as session:
        batch_step_service = BatchStepService(session)
        assert (await batch_step_service.get_step(created.id)).sequence == 1
        assert len(await batch_step_service.list_steps()) == 1

    async with factory() as session:
        updated = await BatchStepService(session).update_step(
            created.id, BatchStepUpdateRequest(written=12), updated_by=ACTOR
        )
        assert updated.written == 12

    read = to_read(created)
    assert read.status == "SUCCEEDED"
    assert read.version == 1
    assert [row.id for row in to_read_list([created])] == [created.id]

    async with factory() as session:
        await BatchStepService(session).delete_step(created.id)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchStepService(session).get_step(missing)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchStepService(session).update_step(
                missing, BatchStepUpdateRequest(written=1), updated_by=ACTOR
            )

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchStepService(session).delete_step(missing)


@pytest.mark.asyncio
async def test_get_batch_step_service_binds_the_request_session(factory) -> None:
    """The DI factory hands an endpoint a service on the request's own session."""
    async with factory() as session:
        batch_step_service = get_batch_step_service(session)
        assert isinstance(batch_step_service, BatchStepService)
        assert batch_step_service.session is session


@pytest.mark.asyncio
async def test_count_run_steps_counts_one_run_only(factory) -> None:
    """The total carries the same filter as the page it describes.

    Another run's steps are in the same table, so a count without the
    `run_id` predicate would report a number no page of this run can reach.
    """
    run_id = await _run_id(factory)
    other_run_id = await _run_id(factory)
    async with factory() as session:
        service = BatchStepService(session)
        for sequence in (1, 2, 3):
            await service.create_finished_step(
                run_id, sequence, 10, ACTOR, range_start=1, range_end=1000, received=1, written=1
            )
        await service.create_finished_step(
            other_run_id, 1, 10, ACTOR, range_start=1, range_end=1000, received=1, written=1
        )

    async with factory() as session:
        service = BatchStepService(session)
        page = await service.list_run_steps(run_id, offset=1, limit=1)
        total = await service.count_run_steps(run_id)

    assert len(page) == 1
    assert total == 3
