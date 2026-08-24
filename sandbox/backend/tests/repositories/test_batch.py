"""BatchRepository tests — CRUD + find_stale."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.models.batch import Batch
from app.repositories.batch import BatchRepository
from app.schemas.batch import BatchCreateInternal, BatchUpdateInternal


@pytest.mark.asyncio
async def test_batch_repository_crud(factory) -> None:
    """The five operations in sequence, ending with a second delete.

    Deleting twice is the interesting part: the repository reports `False`
    instead of raising, which is what lets the service answer 404.
    """
    async with factory() as session:
        repo = BatchRepository(session)
        created = await repo.create(
            BatchCreateInternal(name="A", description="d", created_by="tester")
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
async def test_batch_repository_find_stale(factory) -> None:
    """Two cutoffs around one row prove the comparison direction.

    A reversed `<`/`>` passes any single-cutoff assertion.
    """
    async with factory() as session:
        session.add(Batch(name="old", created_by="tester"))
        await session.commit()
        await session.execute(
            update(Batch).values(created_at=datetime.now(UTC) - timedelta(days=30))
        )
        await session.commit()

    async with factory() as session:
        repo = BatchRepository(session)
        stale = await repo.find_stale(datetime.now(UTC) - timedelta(days=1))
        assert len(stale) == 1
        assert await repo.find_stale(datetime.now(UTC) - timedelta(days=60)) == []
