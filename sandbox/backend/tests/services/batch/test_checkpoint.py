"""BatchCheckpointService tests — CRUD contracts and the resume point the sync reads and writes."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.schemas.batch.checkpoint import (
    BatchCheckpointCreateRequest,
    BatchCheckpointUpdateRequest,
    to_read,
    to_read_list,
)
from app.services.batch.checkpoint import BatchCheckpointService


SOURCE_CODE = "search-barcode-item-info"

SYNCED_BY = "batch:sync_food_barcode_ledger"


@pytest.mark.asyncio
async def test_checkpoint_service_crud(factory) -> None:
    """Each step runs in its own session, as the request lifecycle does.

    A read autobegins a transaction, so reusing one session would make the
    next write's `session.begin()` collide instead of exercising the contract.
    """
    async with factory() as session:
        created = await BatchCheckpointService(session).create_checkpoint(
            BatchCheckpointCreateRequest(source_code=SOURCE_CODE, resume_position=1),
            created_by="tester",
        )
        row_id = created.id

    async with factory() as session:
        stored = await BatchCheckpointService(session).get_checkpoint(row_id)
        assert stored.source_code == SOURCE_CODE

    async with factory() as session:
        assert len(await BatchCheckpointService(session).list_checkpoints()) == 1

    async with factory() as session:
        updated = await BatchCheckpointService(session).update_checkpoint(
            row_id, BatchCheckpointUpdateRequest(resume_position=3001), updated_by="tester"
        )
        assert updated.resume_position == 3001

    async with factory() as session:
        await BatchCheckpointService(session).delete_checkpoint(row_id)

    async with factory() as session:
        assert await BatchCheckpointService(session).list_checkpoints() == []


@pytest.mark.asyncio
async def test_checkpoint_service_missing_row_raises_not_found(factory) -> None:
    """404 is the answer for an id this table does not hold, on all three verbs."""
    missing = uuid4()
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchCheckpointService(session).get_checkpoint(missing)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchCheckpointService(session).update_checkpoint(
                missing, BatchCheckpointUpdateRequest(resume_position=2), updated_by="tester"
            )

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await BatchCheckpointService(session).delete_checkpoint(missing)


@pytest.mark.asyncio
async def test_find_checkpoint_answers_none_without_a_cursor(factory) -> None:
    """Two absences, one answer: no row at all, and a row that carries no offset.

    A checkpoint is the batch layer's common place to record where a job
    stopped, and not every job stops at a *row* — the purge jobs recompute a
    cutoff from the clock and have no offset to store. Deciding here that
    "unknown" means row 1 would put one job's first window in every job's path;
    the caller knows what its own beginning is.
    """
    async with factory() as session:
        assert await BatchCheckpointService(session).find_checkpoint(SOURCE_CODE) is None

    async with factory() as session:
        await BatchCheckpointService(session).create_checkpoint(
            BatchCheckpointCreateRequest(source_code=SOURCE_CODE), "tester"
        )

    async with factory() as session:
        checkpoint = await BatchCheckpointService(session).find_checkpoint(SOURCE_CODE)
    assert checkpoint is not None
    assert (checkpoint.resume_position, checkpoint.resume_key) == (None, None)


@pytest.mark.asyncio
async def test_update_resume_point_creates_then_advances_one_row(factory) -> None:
    """The same call has to serve the first page of a source and the ten-thousandth.

    Two rows for one source would split its checkpoint, and the sync would
    resume from whichever the lookup happened to find.
    """
    async with factory() as session:
        created = await BatchCheckpointService(session).update_resume_point(
            SOURCE_CODE, 1001, "8801234567890:2024001", SYNCED_BY
        )
        assert created.resume_position == 1001
        assert created.created_by == SYNCED_BY

    async with factory() as session:
        advanced = await BatchCheckpointService(session).update_resume_point(
            SOURCE_CODE, 2001, "8801234567891:2024002", SYNCED_BY
        )
        assert advanced.resume_position == 2001
        assert advanced.updated_by == SYNCED_BY

    async with factory() as session:
        batch_checkpoint_service = BatchCheckpointService(session)
        assert len(await batch_checkpoint_service.list_checkpoints()) == 1
        checkpoint = await batch_checkpoint_service.find_checkpoint(SOURCE_CODE)
    assert checkpoint is not None

    # Both halves advance together: an offset kept beside a key from an earlier
    # page would make the next run compare against the wrong record.
    assert (checkpoint.resume_position, checkpoint.resume_key) == (
        2001,
        "8801234567891:2024002",
    )


@pytest.mark.asyncio
async def test_checkpoint_read_schema_exposes_the_version(factory) -> None:
    """A reader of the resume point sees which revision it holds.

    `version` is the optimistic-lock counter: two runs of one job must not
    silently overwrite each other's offset.
    """
    async with factory() as session:
        row = await BatchCheckpointService(session).update_resume_point(
            SOURCE_CODE, 5, None, SYNCED_BY
        )

    async with factory() as session:
        rows = await BatchCheckpointService(session).list_checkpoints()

    read = to_read(row)
    assert read.resume_position == 5
    assert read.version == 1
    assert [item.id for item in to_read_list(rows)] == [row.id]
