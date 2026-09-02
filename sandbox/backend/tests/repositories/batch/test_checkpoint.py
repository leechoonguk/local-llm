"""BatchCheckpointRepository tests — CRUD and the source lookup the sync resumes on."""

import pytest

from app.repositories.batch.checkpoint import BatchCheckpointRepository
from app.schemas.batch.checkpoint import (
    BatchCheckpointCreateInternal,
    BatchCheckpointUpdateInternal,
)


SOURCE_CODE = "search-barcode-item-info"


@pytest.mark.asyncio
async def test_checkpoint_repository_crud(factory) -> None:
    """The five operations in sequence, ending with a second delete.

    Deleting twice is the interesting part: the repository reports `False`
    instead of raising, which is what lets the service answer 404.
    """
    async with factory() as session:
        repo = BatchCheckpointRepository(session)
        created = await repo.create(
            BatchCheckpointCreateInternal(
                source_code=SOURCE_CODE, next_range_start=1, created_by="batch"
            )
        )
        await session.commit()
        row_id = created.id

        got = await repo.get(row_id)
        assert got is not None
        assert got.next_range_start == 1
        assert len(await repo.list()) == 1

        updated = await repo.update(
            row_id, BatchCheckpointUpdateInternal(next_range_start=1001, updated_by="batch")
        )
        assert updated is not None
        assert updated.next_range_start == 1001

        assert await repo.delete(row_id) is True
        await session.commit()
        assert await repo.get(row_id) is None
        assert await repo.delete(row_id) is False
        assert await repo.update(row_id, BatchCheckpointUpdateInternal(updated_by="batch")) is None


@pytest.mark.asyncio
async def test_checkpoint_repository_get_by_source_code(factory) -> None:
    """Each external source resumes on its own row — the sibling ledgers share this table."""
    async with factory() as session:
        repo = BatchCheckpointRepository(session)
        await repo.create(
            BatchCheckpointCreateInternal(
                source_code=SOURCE_CODE, next_range_start=2001, created_by="b"
            )
        )
        await session.commit()

        found = await repo.get_by_source_code(SOURCE_CODE)
        assert found is not None
        assert found.next_range_start == 2001
        assert await repo.get_by_source_code("search-food-item-report") is None
