"""Batch job tests — purge_old_batch_runs against an in-memory engine."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.exceptions import NotFoundError
from app.models.base import Base
from app.models.batch.run import BatchRun
from app.services.batch.run import BatchRunService


CODE = "sync_mfds_ledgers"


@pytest.fixture()
async def test_engine():
    """In-memory engine + tables, replacing app.batch.purge_old_batch_runs.engine."""
    import app.batch.purge_old_batch_runs as batch_runs

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    original = batch_runs.engine
    batch_runs.engine = engine
    yield engine
    batch_runs.engine = original
    await engine.dispose()


async def _finished_run(factory, *, days_ago: int) -> None:
    """A run that ended the given number of days ago."""
    async with factory() as session:
        run = await BatchRunService(session).create_started_run(None, CODE, "CRON", "scheduler")
    async with factory() as session:
        await BatchRunService(session).update_finished_run(run.id, "SUCCEEDED", "scheduler")
    async with factory() as session:
        await session.execute(
            update(BatchRun)
            .where(BatchRun.id == run.id)
            .values(finished_at=datetime.now(UTC) - timedelta(days=days_ago))
        )
        await session.commit()


@pytest.mark.asyncio
async def test_purge_deletes_old_endings_and_keeps_recent_and_running(test_engine) -> None:
    """The cutoff reads the ending, so a live run is unpurgeable by construction.

    Three rows bracket the contract: one past the window (goes), one inside it
    (stays), and one still RUNNING with no ending at all (must stay — deleting
    it would erase an execution that is happening).
    """
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    await _finished_run(factory, days_ago=120)
    await _finished_run(factory, days_ago=5)
    async with factory() as session:
        await BatchRunService(session).create_started_run(None, CODE, "CRON", "scheduler")

    from app.batch.purge_old_batch_runs import purge_old_batch_runs

    assert await purge_old_batch_runs(days=90) == 1

    async with factory() as session:
        remaining = list((await session.execute(select(BatchRun))).scalars().all())
    assert sorted(run.status for run in remaining) == ["RUNNING", "SUCCEEDED"]


@pytest.mark.asyncio
async def test_purge_skips_a_run_deleted_underneath_it(test_engine, monkeypatch) -> None:
    """A row another process already removed is a skip, not a crash."""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    await _finished_run(factory, days_ago=120)

    from app.batch.purge_old_batch_runs import purge_old_batch_runs

    async def _race(self, run_id):
        raise NotFoundError(run_id)

    monkeypatch.setattr(BatchRunService, "delete_run", _race)

    assert await purge_old_batch_runs(days=90) == 0
