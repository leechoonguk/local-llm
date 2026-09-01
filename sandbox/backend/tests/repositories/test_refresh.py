"""RefreshRepository tests — CRUD + get_by_hash + find_stale + revoke_user_tokens."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import update

from app.models.refresh import Refresh
from app.repositories.refresh import RefreshRepository
from app.schemas.refresh import RefreshCreateInternal, RefreshUpdateInternal


def _create_data(user_id, token_hash: str = "digest") -> RefreshCreateInternal:
    return RefreshCreateInternal(
        user_id=user_id,
        expires_at=datetime.now(UTC) + timedelta(days=14),
        token_hash=token_hash,
        created_by="tester",
    )


@pytest.mark.asyncio
async def test_refresh_repository_crud(factory) -> None:
    """The five operations in sequence, ending with a second delete.

    The repeated delete answering `False` is what the service turns into 404.
    """
    user_id = uuid4()
    async with factory() as session:
        repo = RefreshRepository(session)
        created = await repo.create(_create_data(user_id))
        await session.commit()
        refresh_id = created.id
        assert created.token_hash == "digest"

        got = await repo.get(refresh_id)
        assert got is not None
        assert got.id == refresh_id
        assert len(await repo.list()) == 1
        by_hash = await repo.get_by_hash("digest")
        assert by_hash is not None
        assert await repo.get_by_hash("unknown") is None

        revoked_at = datetime.now(UTC)
        updated = await repo.update(
            refresh_id, RefreshUpdateInternal(revoked_at=revoked_at, updated_by="tester")
        )
        assert updated is not None
        assert updated.revoked_at is not None
        assert await repo.update(uuid4(), RefreshUpdateInternal(updated_by="tester")) is None

        assert await repo.delete(refresh_id) is True
        await session.commit()
        assert await repo.get(refresh_id) is None
        assert await repo.delete(refresh_id) is False


@pytest.mark.asyncio
async def test_refresh_repository_find_stale(factory) -> None:
    """Two cutoffs around one row prove the comparison direction."""
    user_id = uuid4()
    async with factory() as session:
        repo = RefreshRepository(session)
        await repo.create(_create_data(user_id))
        await session.commit()
        await session.execute(
            update(Refresh).values(created_at=datetime.now(UTC) - timedelta(days=30))
        )
        await session.commit()

    async with factory() as session:
        repo = RefreshRepository(session)
        stale = await repo.find_stale(datetime.now(UTC) - timedelta(days=1))
        assert len(stale) == 1
        assert len(await repo.find_stale(datetime.now(UTC) - timedelta(days=60))) == 0


@pytest.mark.asyncio
async def test_refresh_repository_revoke_user_tokens_spares_other_users(factory) -> None:
    """Family revocation is scoped to one user and skips already-revoked rows."""
    victim, bystander = uuid4(), uuid4()
    async with factory() as session:
        repo = RefreshRepository(session)
        await repo.create(_create_data(victim, "v1"))
        await repo.create(_create_data(victim, "v2"))
        await repo.create(_create_data(bystander, "b1"))
        await session.commit()

    async with factory() as session:
        repo = RefreshRepository(session)
        await repo.revoke_user_tokens(victim, "test")
        await session.commit()

    async with factory() as session:
        repo = RefreshRepository(session)
        rows = await repo.list()
        by_hash = {row.token_hash: row for row in rows}
        assert by_hash["v1"].revoked_at is not None
        assert by_hash["v2"].revoked_at is not None
        assert by_hash["b1"].revoked_at is None
