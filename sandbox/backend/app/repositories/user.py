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
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sorting import ordered
from app.models.user import User
from app.schemas.user import UserCreateInternal, UserUpdateInternal


# ============================================================
# Classes
# ============================================================


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        username: str | None = None,
        email: str | None = None,
        sort: str | None = None,
        order: str = "asc",
    ) -> list[User]:
        query = ordered(_apply_filters(select(User), username, email), User, sort, order, User.id)
        result = await self.session.execute(query.offset(offset).limit(limit))
        return list(result.scalars().all())

    async def count(self, username: str | None = None, email: str | None = None) -> int:
        """How many rows the unwindowed `list` would return, under the same filters.

        The filters are applied here too, or the footer counts the collection
        while the grid shows a subset of it — "1-3 of 240" on three matching rows.
        """
        query = _apply_filters(select(func.count()).select_from(User), username, email)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def create(self, data: UserCreateInternal) -> User:
        user = User(**data.model_dump())
        self.session.add(user)
        await self.session.flush()
        return user

    async def update(self, user_id: UUID, data: UserUpdateInternal) -> User | None:
        user = await self.session.get(User, user_id)
        if user is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        user.updated_at = datetime.now(UTC)
        await self.session.flush()
        return user

    async def delete(self, user_id: UUID) -> bool:
        user = await self.session.get(User, user_id)
        if user is None:
            return False
        await self.session.delete(user)
        return True


# ============================================================
# Functions
# ============================================================


def _apply_filters(query: Select[Any], username: str | None, email: str | None) -> Select[Any]:
    """Narrow a User query by each field the caller named.

    One builder for the page and its count, because two spellings of the same
    predicate is how a filtered list and its total start disagreeing. The
    filters are combined with AND — each one is a separate box on the screen, so
    filling both must narrow, never widen. `ilike` (never `like`) so the match
    is case-insensitive on every backend, and the wildcards are added here so a
    caller never sends SQL syntax.
    """
    for column, value in ((User.username, username), (User.email, email)):
        if value is not None:
            query = query.where(column.ilike(f"%{value}%"))
    return query
