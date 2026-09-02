"""BatchScheduleRepository tests — CRUD and the scheduler's enabled read."""

import pytest

from app.models.batch.schedule import BatchSchedule
from app.repositories.batch.schedule import BatchScheduleRepository
from app.schemas.batch.schedule import BatchCreateInternal, BatchUpdateInternal


CRON = "0 3 * * *"

JOB_CODE = "purge_expired_refreshes"


@pytest.mark.asyncio
async def test_batch_repository_crud(factory) -> None:
    """The five operations in sequence, ending with a second delete.

    Deleting twice is the interesting part: the repository reports `False`
    instead of raising, which is what lets the service answer 404.
    """
    async with factory() as session:
        repo = BatchScheduleRepository(session)
        created = await repo.create(
            BatchCreateInternal(
                code=JOB_CODE, name="A", description="d", cron=CRON, created_by="tester"
            )
        )
        await session.commit()
        item_id = created.id
        assert created.name == "A"

        got = await repo.get(item_id)
        assert got is not None
        assert got.id == item_id
        assert len(await repo.list()) == 1

        updated = await repo.update(item_id, BatchUpdateInternal(name="B", updated_by="tester"))
        assert updated is not None
        assert updated.name == "B"

        assert await repo.delete(item_id) is True
        await session.commit()
        assert await repo.get(item_id) is None
        assert await repo.delete(item_id) is False


@pytest.mark.asyncio
async def test_batch_repository_list_enabled(factory) -> None:
    """Only enabled rows come back — a disabled job that still schedules is the bug."""
    async with factory() as session:
        session.add(BatchSchedule(code=JOB_CODE, name="on", cron=CRON, created_by="tester"))
        session.add(
            BatchSchedule(code=JOB_CODE, name="off", cron=CRON, enabled=False, created_by="tester")
        )
        await session.commit()

    async with factory() as session:
        enabled = await BatchScheduleRepository(session).list_enabled()
        assert [batch.name for batch in enabled] == ["on"]
