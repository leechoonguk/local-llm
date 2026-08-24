"""UserRepository tests — CRUD + find_stale + get_by_username/email."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreateInternal, UserUpdateInternal


@pytest.mark.asyncio
async def test_user_repository_crud(factory) -> None:
    """The five operations in sequence, ending with a second delete.

    The repeated delete answering `False` is what the service turns into 404.
    """
    async with factory() as session:
        repo = UserRepository(session)
        created = await repo.create(
            UserCreateInternal(
                username="u", email="u@example.com", hashed_password="x", created_by="tester"
            )
        )
        await session.commit()
        user_id = created.id
        assert created.username == "u"

        got = await repo.get(user_id)
        assert got is not None
        assert got.id == user_id
        assert len(await repo.list()) == 1

        updated = await repo.update(
            user_id, UserUpdateInternal(email="new@example.com", updated_by="tester")
        )
        assert updated is not None
        assert updated.email == "new@example.com"

        assert await repo.delete(user_id) is True
        await session.commit()
        assert await repo.get(user_id) is None
        assert await repo.delete(user_id) is False


@pytest.mark.asyncio
async def test_user_repository_find_stale(factory) -> None:
    """Two cutoffs around one row prove the comparison direction."""
    async with factory() as session:
        session.add(User(username="old", email="old@example.com", hashed_password="x"))
        await session.commit()
        await session.execute(
            update(User).values(created_at=datetime.now(UTC) - timedelta(days=30))
        )
        await session.commit()

    async with factory() as session:
        repo = UserRepository(session)
        stale = await repo.find_stale(datetime.now(UTC) - timedelta(days=1))
        assert len(stale) == 1
        assert await repo.find_stale(datetime.now(UTC) - timedelta(days=60)) == []


@pytest.mark.asyncio
async def test_user_repository_get_by_username_and_email(factory) -> None:
    """Both lookups answer None for a miss instead of raising.

    Login and the conflict check both depend on that: a raise would turn a
    free username into a 500.
    """
    async with factory() as session:
        session.add(User(username="bob", email="bob@example.com", hashed_password="x"))
        await session.commit()

    async with factory() as session:
        repo = UserRepository(session)
        assert (await repo.get_by_username("bob")) is not None
        assert (await repo.get_by_username("missing")) is None
        assert (await repo.get_by_email("bob@example.com")) is not None
        assert (await repo.get_by_email("missing@example.com")) is None
