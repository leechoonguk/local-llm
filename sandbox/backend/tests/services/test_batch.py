"""BatchService tests — every public method (success + error)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import NotFoundError
from app.models.batch import Batch
from app.schemas.batch import BatchCreateRequest, BatchUpdateRequest
from app.services.batch import BatchService


MISSING_UUID = uuid4()


@pytest.mark.asyncio
async def test_batch_service_crud(factory) -> None:
    """Each step runs in its own session, as a request would.

    Reusing one session would hide identity-map effects: an object still cached
    from the create makes a later read pass without touching the database.
    """
    async with factory() as session:
        created = await BatchService(session).create_batch(
            BatchCreateRequest(name="A", description="d"), "tester"
        )
        item_id = created.id
        assert created.name == "A"
        assert created.created_by == "tester"

    async with factory() as session:
        svc = BatchService(session)
        got = await svc.get_batch(item_id)
        assert got.id == item_id
        assert len(await svc.list_batches()) == 1

    async with factory() as session:
        updated = await BatchService(session).update_batch(
            item_id, BatchUpdateRequest(name="B"), "tester"
        )
        assert updated.name == "B"

    async with factory() as session:
        await BatchService(session).delete_batch(item_id)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchService(session).get_batch(item_id)


@pytest.mark.asyncio
async def test_batch_service_not_found(factory) -> None:
    """Read, update and delete of a missing id all raise the same domain error.

    That uniformity is what lets one handler answer 404 for every path.
    """
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchService(session).get_batch(MISSING_UUID)
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchService(session).update_batch(
                MISSING_UUID, BatchUpdateRequest(name="x"), "tester"
            )
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchService(session).delete_batch(MISSING_UUID)


@pytest.mark.asyncio
async def test_batch_service_find_stale(factory) -> None:
    """find_stale returns only batches created before the cutoff."""
    async with factory() as session:
        service = BatchService(session)
        old = await service.create_batch(BatchCreateRequest(name="old"), "tester")
    async with factory() as session:
        batch = await session.get(Batch, old.id)
        batch.created_at = datetime.now(UTC) - timedelta(days=10)
        await session.commit()
    async with factory() as session:
        service = BatchService(session)
        await service.create_batch(BatchCreateRequest(name="fresh"), "tester")
        cutoff = datetime.now(UTC) - timedelta(days=1)
        stale = await service.find_stale(cutoff)
        assert [b.name for b in stale] == ["old"]


@pytest.mark.asyncio
async def test_concurrent_update_raises_stale_data(factory) -> None:
    """Two transactions loading the same row: the slower commit is rejected.

    Without version_id_col the second UPDATE would silently overwrite the
    first one's columns (lost update).
    """
    async with factory() as session:
        created = await BatchService(session).create_batch(BatchCreateRequest(name="seed"), "a")
    assert created.version == 1

    first = factory()
    second = factory()
    try:
        loaded_first = await first.get(Batch, created.id)
        loaded_second = await second.get(Batch, created.id)

        loaded_first.name = "winner"
        await first.commit()
        assert loaded_first.version == 2

        loaded_second.name = "loser"
        with pytest.raises(StaleDataError):
            await second.commit()
    finally:
        await first.close()
        await second.close()

    async with factory() as session:
        survivor = await session.get(Batch, created.id)
        assert survivor.name == "winner"
        assert survivor.version == 2
