# ============================================================
# Imports
# ============================================================

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.security import create_refresh_token, hash_refresh_token, refresh_token_expires_at
from app.models.refresh import Refresh
from app.repositories.refresh import RefreshRepository
from app.schemas.refresh import (
    RefreshCreateInternal,
    RefreshCreateRequest,
    RefreshUpdateInternal,
    RefreshUpdateRequest,
)


# ============================================================
# Classes
# ============================================================


class RefreshService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.refresh_repository = RefreshRepository(session)

    async def get_refresh(self, refresh_id: UUID) -> Refresh:
        refresh = await self.refresh_repository.get(refresh_id)
        if refresh is None:
            raise NotFoundError(refresh_id)
        return refresh

    async def list_refreshes(self, offset: int = 0, limit: int = 100) -> list[Refresh]:
        return await self.refresh_repository.list(offset, limit)

    async def find_expired(self, expired_before: datetime) -> list[Refresh]:
        """Return tokens expired before the given moment — used by batch jobs."""
        return await self.refresh_repository.find_expired(expired_before)

    async def create_refresh(self, data: RefreshCreateRequest, created_by: str) -> str:
        """Issue a token for a session and return the secret, once.

        The caller gets the only copy that will ever exist — the row keeps the
        digest — so a lost value cannot be recovered, only replaced by a new
        login.
        """
        token = create_refresh_token()
        internal = RefreshCreateInternal(
            user_id=data.user_id,
            expires_at=refresh_token_expires_at(),
            token_hash=hash_refresh_token(token),
            created_by=created_by,
        )
        async with self.session.begin():
            await self.refresh_repository.create(internal)
        return token

    async def create_rotated_refresh(self, token: str | None, created_by: str) -> tuple[UUID, str]:
        """Spend one refresh token and issue its successor.

        Rotation is the whole point of storing the token: a refresh token that
        survives its own use is a long-lived bearer credential, so a stolen copy
        is worth as much as the password. Here the presented token is revoked in
        the same transaction that mints the next one.

        A token presented **twice** is the observable signature of theft — the
        legitimate client and the thief cannot both hold the newest one — so the
        second presentation revokes every live token of that user rather than
        just failing: the session dies for both, and the user logs in again.

        A missing token fails exactly like a rejected one: no cookie, an unknown
        digest and an expired row are one answer, so nothing here tells a caller
        which of the three it hit.
        """
        if token is None:
            raise AuthenticationError()
        successor: str | None = None
        user_id: UUID | None = None
        # The 401 is raised OUTSIDE the transaction on purpose: raising inside
        # `session.begin()` rolls the block back, and the one write that must
        # survive a rejected request is the theft response — un-revoking the
        # family while telling the caller "no" would hand the thief another try.
        async with self.session.begin():
            stored = await self.refresh_repository.get_by_hash(hash_refresh_token(token))
            if stored is not None and stored.revoked_at is not None:
                await self.refresh_repository.revoke_user_tokens(stored.user_id, created_by)
                stored = None
            if stored is not None:
                # DateTime(timezone=True) comes back aware from Postgres but naive
                # from SQLite (the test engine); the stored value is UTC either way,
                # so pin the zone before comparing instead of trusting the driver.
                expires_at = (
                    stored.expires_at
                    if stored.expires_at.tzinfo is not None
                    else stored.expires_at.replace(tzinfo=UTC)
                )
                if expires_at <= datetime.now(UTC):
                    stored = None
            if stored is not None:
                successor = create_refresh_token()
                await self.refresh_repository.update(
                    stored.id,
                    RefreshUpdateInternal(revoked_at=datetime.now(UTC), updated_by=created_by),
                )
                await self.refresh_repository.create(
                    RefreshCreateInternal(
                        user_id=stored.user_id,
                        expires_at=refresh_token_expires_at(),
                        token_hash=hash_refresh_token(successor),
                        created_by=created_by,
                    )
                )
                user_id = stored.user_id
        if user_id is None or successor is None:
            raise AuthenticationError()
        return user_id, successor

    async def update_refresh(
        self, refresh_id: UUID, data: RefreshUpdateRequest, updated_by: str
    ) -> Refresh:
        internal = RefreshUpdateInternal(
            **data.model_dump(exclude_unset=True), updated_by=updated_by
        )
        async with self.session.begin():
            refresh = await self.refresh_repository.update(refresh_id, internal)
            if refresh is None:
                raise NotFoundError(refresh_id)
            return refresh

    async def delete_refresh(self, refresh_id: UUID) -> None:
        async with self.session.begin():
            if not await self.refresh_repository.delete(refresh_id):
                raise NotFoundError(refresh_id)

    async def delete_session(self, token: str | None, revoked_by: str) -> None:
        """Revoke the token a logging-out client presents.

        Silent about an unknown or missing token on purpose: logout is the one
        request a client must always be able to complete, and answering "that
        token does not exist" would turn this endpoint into an oracle that tells
        an attacker which stolen values are live.
        """
        if token is None:
            return
        async with self.session.begin():
            stored = await self.refresh_repository.get_by_hash(hash_refresh_token(token))
            if stored is None or stored.revoked_at is not None:
                return
            await self.refresh_repository.update(
                stored.id,
                RefreshUpdateInternal(revoked_at=datetime.now(UTC), updated_by=revoked_by),
            )
