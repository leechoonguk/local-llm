# ============================================================
# Imports
# ============================================================

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def list(self, offset: int = 0, limit: int = 100) -> list[User]:
        result = await self.session.execute(select(User).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def count(self) -> int:
        """How many rows the unwindowed `list` would return."""
        result = await self.session.execute(select(func.count()).select_from(User))
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
