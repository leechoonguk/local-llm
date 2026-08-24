# ============================================================
# Imports
# ============================================================

from uuid import UUID

from anyio import to_thread
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import (
    UserCreateInternal,
    UserCreateRequest,
    UserUpdateInternal,
    UserUpdateRequest,
)


# ============================================================
# Classes
# ============================================================

class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repository = UserRepository(session)

    async def get_user(self, user_id: UUID) -> User:
        user = await self.user_repository.get(user_id)
        if user is None:
            raise NotFoundError(user_id)
        return user

    async def get_by_username(self, username: str) -> User | None:
        return await self.user_repository.get_by_username(username)

    async def authenticate(self, username: str, password: str) -> User:
        """Verify credentials and return the user, or raise AuthenticationError."""
        user = await self.user_repository.get_by_username(username)
        # argon2 costs ~25 ms of CPU (measured). Run in the event loop it stalls
        # every other request in the process for that long, so it goes to a
        # worker thread.
        if user is None or not await to_thread.run_sync(
            verify_password, password, user.hashed_password
        ):
            raise AuthenticationError()
        return user

    async def list_users(self, offset: int = 0, limit: int = 100) -> list[User]:
        return await self.user_repository.list(offset, limit)

    async def create_user(self, data: UserCreateRequest, created_by: str) -> User:
        internal = UserCreateInternal(
            username=data.username,
            email=data.email,
            hashed_password=await to_thread.run_sync(hash_password, data.password),
            created_by=created_by,
        )
        async with self.session.begin():
            if await self.user_repository.get_by_username(data.username) is not None:
                raise ConflictError(f"Username '{data.username}' already exists")
            if await self.user_repository.get_by_email(data.email) is not None:
                raise ConflictError(f"Email '{data.email}' already exists")
            return await self.user_repository.create(internal)

    async def update_user(self, user_id: UUID, data: UserUpdateRequest, updated_by: str) -> User:
        internal = UserUpdateInternal(**data.model_dump(exclude_unset=True), updated_by=updated_by)
        async with self.session.begin():
            user = await self.user_repository.update(user_id, internal)
            if user is None:
                raise NotFoundError(user_id)
            return user

    async def delete_user(self, user_id: UUID) -> None:
        async with self.session.begin():
            if not await self.user_repository.delete(user_id):
                raise NotFoundError(user_id)
