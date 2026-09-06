"""UserService tests — every public method (success + error)."""

from uuid import uuid4

import pytest

from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.schemas.user import UserCreateRequest, UserUpdateRequest
from app.services.user import UserService


MISSING_UUID = uuid4()


@pytest.mark.asyncio
async def test_user_service_crud(factory) -> None:
    """Each step runs in its own session, as a request would.

    A single shared session would let the identity map answer reads that never
    reached the database.
    """
    async with factory() as session:
        created = await UserService(session).create_user(
            UserCreateRequest(username="alice", email="alice@example.com", password="secret-pass"),
            "system",
        )
        user_id = created.id
        assert created.username == "alice"

    async with factory() as session:
        svc = UserService(session)
        got = await svc.get_user(user_id)
        assert got.id == user_id
        assert len(await svc.list_users()) == 1
        by_name = await svc.get_by_username("alice")
        assert by_name is not None
        assert await svc.get_by_username("missing") is None

    async with factory() as session:
        updated = await UserService(session).update_user(
            user_id, UserUpdateRequest(email="new@example.com"), "system"
        )
        assert updated.email == "new@example.com"

    async with factory() as session:
        await UserService(session).delete_user(user_id)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await UserService(session).get_user(user_id)


@pytest.mark.asyncio
async def test_user_service_authenticate(factory) -> None:
    """Wrong password and unknown user fail identically.

    Any difference between them enumerates accounts for an attacker.
    """
    async with factory() as session:
        await UserService(session).create_user(
            UserCreateRequest(username="bob", email="bob@example.com", password="secret-pass"),
            "system",
        )
    async with factory() as session:
        user = await UserService(session).authenticate("bob", "secret-pass")
        assert user.username == "bob"
    async with factory() as session:
        with pytest.raises(AuthenticationError):
            await UserService(session).authenticate("bob", "wrong")
    async with factory() as session:
        with pytest.raises(AuthenticationError):
            await UserService(session).authenticate("ghost", "secret")


@pytest.mark.asyncio
async def test_user_service_conflicts(factory) -> None:
    """Username and email are checked separately, before the insert.

    Letting the database raise instead would surface as 500, not 409.
    """
    async with factory() as session:
        await UserService(session).create_user(
            UserCreateRequest(username="dup", email="a@example.com", password="secret-pass"),
            "system",
        )
    async with factory() as session:
        with pytest.raises(ConflictError):
            await UserService(session).create_user(
                UserCreateRequest(username="dup", email="b@example.com", password="secret-pass"),
                "system",
            )
    async with factory() as session:
        with pytest.raises(ConflictError):
            await UserService(session).create_user(
                UserCreateRequest(username="other", email="a@example.com", password="secret-pass"),
                "system",
            )


@pytest.mark.asyncio
async def test_user_service_not_found(factory) -> None:
    """Read, update and delete of a missing id raise the same domain error."""
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await UserService(session).get_user(MISSING_UUID)
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await UserService(session).update_user(
                MISSING_UUID, UserUpdateRequest(email="x@example.com"), "system"
            )
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await UserService(session).delete_user(MISSING_UUID)


@pytest.mark.asyncio
async def test_count_users_ignores_the_window(factory) -> None:
    """The total is the collection's size, not the page's.

    A count that inherited `offset`/`limit` would agree with `list_users` on
    every page that happens to hold everything, and disagree exactly when the
    footer needs it — so the assertion pages deliberately.
    """
    async with factory() as session:
        service = UserService(session)
        for index in range(3):
            await service.create_user(
                UserCreateRequest(
                    username=f"counted-{index}",
                    email=f"counted-{index}@example.com",
                    password="secret-pass",
                ),
                "tester",
            )

    async with factory() as session:
        service = UserService(session)
        page = await service.list_users(offset=1, limit=1)
        total = await service.count_users()

    assert len(page) == 1
    assert total == 3


@pytest.mark.asyncio
async def test_list_users_filters_each_field_and_the_total(factory) -> None:
    """Each filter narrows its own column, case-insensitively, and the total follows.

    Both filters together are asserted because they are separate boxes on the
    screen: combined with OR they would *widen* the result when a reader adds a
    second condition. The total is asserted beside the page because the count is
    a second query - a filter applied to the rows and not to the count reads as
    "1-1 of 3", the footer describing a collection the grid is no longer showing.
    """
    async with factory() as session:
        service = UserService(session)
        for username, email in (
            ("Ada", "ada@example.com"),
            ("grace", "grace@lovelace.test"),
            ("linus", "linus@example.com"),
        ):
            await service.create_user(
                UserCreateRequest(username=username, email=email, password="secret-pass"),
                "tester",
            )

    async with factory() as session:
        service = UserService(session)
        by_name = await service.list_users(username="ada")
        by_email = await service.list_users(email="LOVELACE")
        both = await service.list_users(username="grace", email="example.com")
        unfiltered = await service.count_users()
        filtered = await service.count_users(email="example.com")
        missing = await service.list_users(username="nobody")

    assert [user.username for user in by_name] == ["Ada"]
    assert [user.username for user in by_email] == ["grace"]
    assert both == []
    assert unfiltered == 3
    assert filtered == 2
    assert missing == []
