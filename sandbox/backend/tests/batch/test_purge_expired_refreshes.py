"""Batch job tests — purge_expired_refreshes against an in-memory engine."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.exceptions import NotFoundError
from app.models.base import Base
from app.models.refresh import Refresh
from app.models.user import User
from app.services.refresh import RefreshService


@pytest.fixture()
async def test_engine():
    """In-memory engine + tables, replacing app.batch.purge_expired_refreshes.engine."""
    import app.batch.purge_expired_refreshes as batch_purge_expired_refreshes

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Swap the module-level engine so the job hits the test DB.
    original = batch_purge_expired_refreshes.engine
    batch_purge_expired_refreshes.engine = engine
    yield engine
    batch_purge_expired_refreshes.engine = original
    await engine.dispose()


async def _seed_user(factory) -> UUID:
    """A token needs an owner: `refresh.user_id` is a NOT NULL foreign key."""
    async with factory() as session:
        user = User(username="tester", email="tester@example.com", hashed_password="x")
        session.add(user)
        await session.commit()
        return user.id


def _token(user_id: UUID, token_hash: str, expires_at: datetime) -> Refresh:
    """A stored token with the only field the purge reads — its own expiry."""
    return Refresh(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_by="tester",
    )


@pytest.mark.asyncio
async def test_purge_expired_refreshes_deletes_past_the_grace_window(test_engine) -> None:
    """The cutoff is the whole point: a job that deletes everything logs users out.

    One token expired long ago, one expires tomorrow, so an off-by-one in the
    comparison shows up as a wrong survivor rather than a passing count.
    """
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    user_id = await _seed_user(factory)
    async with factory() as session:
        session.add(_token(user_id, "old", datetime.now(UTC) - timedelta(days=60)))
        session.add(_token(user_id, "live", datetime.now(UTC) + timedelta(days=1)))
        await session.commit()

    from app.batch.purge_expired_refreshes import purge_expired_refreshes

    deleted = await purge_expired_refreshes(days=30)

    assert deleted == 1
    async with factory() as session:
        remaining = list((await session.execute(select(Refresh))).scalars().all())
    assert [row.token_hash for row in remaining] == ["live"]


@pytest.mark.asyncio
async def test_purge_keeps_recently_expired_tokens(test_engine) -> None:
    """Inside the grace window a revoked row still answers "this token was used"."""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    user_id = await _seed_user(factory)
    async with factory() as session:
        session.add(_token(user_id, "yesterday", datetime.now(UTC) - timedelta(days=1)))
        await session.commit()

    from app.batch.purge_expired_refreshes import purge_expired_refreshes

    assert await purge_expired_refreshes(days=30) == 0


@pytest.mark.asyncio
async def test_purge_skips_already_deleted(test_engine, monkeypatch) -> None:
    """A token whose delete raises NotFoundError is skipped, not fatal."""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    user_id = await _seed_user(factory)
    async with factory() as session:
        session.add(_token(user_id, "race", datetime.now(UTC) - timedelta(days=60)))
        await session.commit()

    from app.batch.purge_expired_refreshes import purge_expired_refreshes

    async def _delete_race(self, refresh_id):
        raise NotFoundError(refresh_id)

    monkeypatch.setattr(RefreshService, "delete_refresh", _delete_race)

    assert await purge_expired_refreshes(days=30) == 0
