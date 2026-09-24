"""BatchScheduleService tests — every public method (success + error)."""

from uuid import uuid4

import pytest
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import NotFoundError
from app.models.batch.schedule import BatchSchedule
from app.schemas.batch.schedule import BatchCreateRequest, BatchUpdateRequest
from app.services.batch.schedule import BatchScheduleService


MISSING_UUID = uuid4()

CRON = "0 3 * * *"

JOB_CODE = "purge_expired_refreshes"


@pytest.mark.asyncio
async def test_batch_service_crud(factory) -> None:
    """Each step runs in its own session, as a request would.

    Reusing one session would hide identity-map effects: an object still cached
    from the create makes a later read pass without touching the database.
    """
    async with factory() as session:
        created = await BatchScheduleService(session).create_batch(
            BatchCreateRequest(code=JOB_CODE, cron=CRON), "tester"
        )
        item_id = created.id
        assert created.code == JOB_CODE
        assert created.created_by == "tester"

    async with factory() as session:
        svc = BatchScheduleService(session)
        got = await svc.get_batch(item_id)
        assert got.id == item_id
        assert len(await svc.list_batches()) == 1

    async with factory() as session:
        updated = await BatchScheduleService(session).update_batch(
            item_id, BatchUpdateRequest(cron="30 4 * * *"), "tester"
        )
        assert updated.cron == "30 4 * * *"

    async with factory() as session:
        await BatchScheduleService(session).delete_batch(item_id)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchScheduleService(session).get_batch(item_id)


@pytest.mark.asyncio
async def test_batch_service_not_found(factory) -> None:
    """Read, update and delete of a missing id all raise the same domain error.

    That uniformity is what lets one handler answer 404 for every path.
    """
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchScheduleService(session).get_batch(MISSING_UUID)
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchScheduleService(session).update_batch(
                MISSING_UUID, BatchUpdateRequest(cron="30 4 * * *"), "tester"
            )
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchScheduleService(session).delete_batch(MISSING_UUID)


@pytest.mark.asyncio
async def test_concurrent_update_raises_stale_data(factory) -> None:
    """Two transactions loading the same row: the slower commit is rejected.

    Without version_id_col the second UPDATE would silently overwrite the
    first one's columns (lost update).
    """
    async with factory() as session:
        created = await BatchScheduleService(session).create_batch(
            BatchCreateRequest(code=JOB_CODE, cron=CRON), "a"
        )
    assert created.version == 1

    first = factory()
    second = factory()
    try:
        loaded_first = await first.get(BatchSchedule, created.id)
        loaded_second = await second.get(BatchSchedule, created.id)

        loaded_first.cron = "0 1 * * *"
        await first.commit()
        assert loaded_first.version == 2

        loaded_second.cron = "0 2 * * *"
        with pytest.raises(StaleDataError):
            await second.commit()
    finally:
        await first.close()
        await second.close()

    async with factory() as session:
        survivor = await session.get(BatchSchedule, created.id)
        assert survivor.cron == "0 1 * * *"
        assert survivor.version == 2


@pytest.mark.asyncio
async def test_batch_service_list_enabled_batches(factory) -> None:
    """The startup read returns the running schedule, not the whole table."""
    async with factory() as session:
        service = BatchScheduleService(session)
        await service.create_batch(BatchCreateRequest(code=JOB_CODE, cron=CRON), "tester")
        stopped = await service.create_batch(
            BatchCreateRequest(code=JOB_CODE, cron="0 5 * * *"), "tester"
        )

    async with factory() as session:
        await BatchScheduleService(session).update_batch(
            stopped.id, BatchUpdateRequest(enabled=False), "tester"
        )

    async with factory() as session:
        enabled = await BatchScheduleService(session).list_enabled_batches()
        assert [batch.cron for batch in enabled] == [CRON]


@pytest.mark.asyncio
async def test_count_batches_ignores_the_window(factory) -> None:
    """The total is the collection's size, not the page's."""
    async with factory() as session:
        service = BatchScheduleService(session)
        for cron in ("0 1 * * *", "0 2 * * *", "0 3 * * *"):
            await service.create_batch(BatchCreateRequest(code=JOB_CODE, cron=cron), "tester")

    async with factory() as session:
        service = BatchScheduleService(session)
        page = await service.list_batches(offset=2, limit=1)
        total = await service.count_batches()

    assert len(page) == 1
    assert total == 3
