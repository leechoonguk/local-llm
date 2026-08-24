"""Batch job tests — purge_stale_batches against an in-memory engine."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.exceptions import NotFoundError
from app.models.base import Base
from app.models.batch import Batch
from app.services.batch import BatchService


@pytest.fixture()
async def test_engine():
    """In-memory engine + tables, replacing app.batch.batches.engine."""
    import app.batch.batches as batch_batches

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Swap the module-level engine so purge_stale_batches hits the test DB.
    original = batch_batches.engine
    batch_batches.engine = engine
    yield engine
    batch_batches.engine = original
    await engine.dispose()


@pytest.mark.asyncio
async def test_purge_stale_batches_deletes_old_only(test_engine) -> None:
    """The cutoff is the whole point: a job that deletes everything is data loss.

    One row is older than the window and one is not, so an off-by-one in the
    comparison shows up as a wrong survivor rather than a passing count.
    """
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        old = Batch(name="Old batch", created_by="tester")
        old.created_at = datetime.now(UTC) - timedelta(days=60)
        session.add(old)
        fresh = Batch(name="Fresh batch", created_by="tester")
        session.add(fresh)
        await session.commit()

    from app.batch.batches import purge_stale_batches

    deleted = await purge_stale_batches(days=30)

    assert deleted == 1
    async with factory() as session:
        remaining = list((await session.execute(select(Batch))).scalars().all())
    names = {b.name for b in remaining}
    assert "Fresh batch" in names
    assert "Old batch" not in names


@pytest.mark.asyncio
async def test_purge_stale_batches_no_stale(test_engine) -> None:
    """Nothing to purge must answer 0, not fail — the job runs nightly."""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add(Batch(name="New batch", created_by="tester"))
        await session.commit()

    from app.batch.batches import purge_stale_batches

    assert await purge_stale_batches(days=30) == 0


@pytest.mark.asyncio
async def test_purge_skips_already_deleted(test_engine, monkeypatch) -> None:
    """A stale batch whose delete raises NotFoundError is skipped, not fatal."""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add(Batch(name="race batch", created_by="tester"))
        await session.commit()
        await session.execute(
            update(Batch).values(created_at=datetime.now(UTC) - timedelta(days=30))
        )
        await session.commit()

    from app.batch.batches import purge_stale_batches

    async def _delete_race(self, batch_id):
        raise NotFoundError(batch_id)

    monkeypatch.setattr(BatchService, "delete_batch", _delete_race)

    deleted = await purge_stale_batches(days=30)
    assert deleted == 0
