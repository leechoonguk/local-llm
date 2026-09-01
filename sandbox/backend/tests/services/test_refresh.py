"""RefreshService tests — every public method (success + error)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import update

from app.core.exceptions import AuthenticationError, NotFoundError
from app.models.refresh import Refresh
from app.schemas.refresh import RefreshCreateRequest, RefreshUpdateRequest
from app.services.refresh import RefreshService


MISSING_UUID = uuid4()


@pytest.mark.asyncio
async def test_refresh_service_crud(factory) -> None:
    """Each step runs in its own session, as a request would."""
    user_id = uuid4()
    async with factory() as session:
        token = await RefreshService(session).create_refresh(
            RefreshCreateRequest(user_id=user_id), "system"
        )
        assert isinstance(token, str) and token != ""

    async with factory() as session:
        svc = RefreshService(session)
        rows = await svc.list_refreshes()
        assert len(rows) == 1
        refresh_id = rows[0].id
        got = await svc.get_refresh(refresh_id)
        assert got.user_id == user_id

    async with factory() as session:
        revoked_at = datetime.now(UTC)
        updated = await RefreshService(session).update_refresh(
            refresh_id, RefreshUpdateRequest(revoked_at=revoked_at), "system"
        )
        assert updated.revoked_at is not None

    async with factory() as session:
        await RefreshService(session).delete_refresh(refresh_id)

    # One session per error case: a read's autobegin would otherwise still hold
    # the session when the next method opens its own transaction.
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await RefreshService(session).get_refresh(refresh_id)
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await RefreshService(session).update_refresh(
                MISSING_UUID, RefreshUpdateRequest(), "system"
            )
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await RefreshService(session).delete_refresh(MISSING_UUID)


@pytest.mark.asyncio
async def test_rotate_rejects_expired_token(factory) -> None:
    """An expired row answers exactly like a missing one — one 401, no oracle."""
    user_id = uuid4()
    async with factory() as session:
        token = await RefreshService(session).create_refresh(
            RefreshCreateRequest(user_id=user_id), "system"
        )
    async with factory() as session:
        await session.execute(
            update(Refresh).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    async with factory() as session:
        with pytest.raises(AuthenticationError):
            await RefreshService(session).create_rotated_refresh(token, "refresh")


@pytest.mark.asyncio
async def test_delete_session_is_silent_for_unknown_and_revoked(factory) -> None:
    """Logout never reveals whether the presented value was live."""
    user_id = uuid4()
    async with factory() as session:
        svc = RefreshService(session)
        await svc.delete_session(None, "logout")
        await svc.delete_session("never-issued", "logout")

    async with factory() as session:
        token = await RefreshService(session).create_refresh(
            RefreshCreateRequest(user_id=user_id), "system"
        )
    async with factory() as session:
        await RefreshService(session).delete_session(token, "logout")
    async with factory() as session:
        # A second delete of the same (now revoked) token is still silent.
        await RefreshService(session).delete_session(token, "logout")
        rows = await RefreshService(session).list_refreshes()
        assert rows[0].revoked_at is not None


@pytest.mark.asyncio
async def test_refresh_read_projection(factory) -> None:
    """`to_read` must never leak the digest — the read shape is the contract."""
    from app.schemas.refresh import to_read, to_read_list

    user_id = uuid4()
    async with factory() as session:
        await RefreshService(session).create_refresh(
            RefreshCreateRequest(user_id=user_id), "system"
        )
    async with factory() as session:
        rows = await RefreshService(session).list_refreshes()
        read = to_read(rows[0])
        assert read.user_id == user_id
        assert not hasattr(read, "token_hash")
        assert [r.id for r in to_read_list(rows)] == [rows[0].id]
