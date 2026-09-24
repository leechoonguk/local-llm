# ============================================================
# Imports
# ============================================================

# Deferred annotations, as every other repository declares them. Without it a
# `-> list[...]` written after this class's own `list` method resolves to that
# method instead of the builtin: the class body is a scope, and the name is
# taken there first. Python 3.14 evaluates annotations lazily so nothing broke
# at runtime, and the two repositories that lacked this line were the only two
# a type checker could see it in.
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh import Refresh
from app.schemas.refresh import RefreshCreateInternal, RefreshUpdateInternal


# ============================================================
# Classes
# ============================================================


class RefreshRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, refresh_id: UUID) -> Refresh | None:
        return await self.session.get(Refresh, refresh_id)

    async def get_by_hash(self, token_hash: str) -> Refresh | None:
        result = await self.session.execute(select(Refresh).where(Refresh.token_hash == token_hash))
        return result.scalar_one_or_none()

    async def list(self, offset: int = 0, limit: int = 100) -> list[Refresh]:
        result = await self.session.execute(select(Refresh).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def find_expired(self, expired_before: datetime) -> list[Refresh]:
        """Return tokens whose own expiry is already past the given moment.

        Keyed on `expires_at`, never on `created_at`: the lifetime is a setting,
        so a purge that measured age from creation would delete live sessions
        the day someone raised it.
        """
        result = await self.session.execute(
            select(Refresh).where(Refresh.expires_at < expired_before)
        )
        return list(result.scalars().all())

    async def create(self, data: RefreshCreateInternal) -> Refresh:
        refresh = Refresh(**data.model_dump())
        self.session.add(refresh)
        await self.session.flush()
        return refresh

    async def update(self, refresh_id: UUID, data: RefreshUpdateInternal) -> Refresh | None:
        refresh = await self.session.get(Refresh, refresh_id)
        if refresh is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(refresh, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        refresh.updated_at = datetime.now(UTC)
        await self.session.flush()
        return refresh

    async def revoke_user_tokens(self, user_id: UUID, revoked_by: str) -> None:
        """Revoke every live token of one user, in one statement.

        Reuse detection revokes a whole family at once. Loading the rows to set
        an attribute each would issue one UPDATE per row and bump `version`
        through the optimistic-lock mapper for a state no reader compares.
        """
        revoked_at = datetime.now(UTC)
        await self.session.execute(
            update(Refresh)
            .where(Refresh.user_id == user_id, Refresh.revoked_at.is_(None))
            .values(revoked_at=revoked_at, updated_at=revoked_at, updated_by=revoked_by)
        )

    async def delete(self, refresh_id: UUID) -> bool:
        refresh = await self.session.get(Refresh, refresh_id)
        if refresh is None:
            return False
        await self.session.delete(refresh)
        return True
