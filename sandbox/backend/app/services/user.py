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
# Constants
# ============================================================

#: A form puts each of these on the field that owns it, which one shared
#: `conflict` code could not do.
USERNAME_TAKEN_CODE = "username_taken"

EMAIL_TAKEN_CODE = "email_taken"


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
        # Detach the user so the caller can open its own transaction via
        # session.begin() — the lookup's autobegin would otherwise still hold
        # the session (same idiom as get_current_user; rollback would expire
        # the attributes of an attached instance).
        self.session.expunge(user)
        await self.session.rollback()
        return user

    async def list_users(
        self,
        offset: int = 0,
        limit: int = 100,
        username: str | None = None,
        email: str | None = None,
    ) -> list[User]:
        return await self.user_repository.list(offset, limit, username, email)

    async def count_users(self, username: str | None = None, email: str | None = None) -> int:
        """The collection's size under the filters the caller just applied."""
        return await self.user_repository.count(username, email)

    async def create_user(self, data: UserCreateRequest, created_by: str) -> User:
        internal = UserCreateInternal(
            username=data.username,
            email=data.email,
            hashed_password=await to_thread.run_sync(hash_password, data.password),
            created_by=created_by,
        )
        async with self.session.begin():
            if await self.user_repository.get_by_username(data.username) is not None:
                raise ConflictError(
                    f"Username '{data.username}' already exists", USERNAME_TAKEN_CODE
                )
            if await self.user_repository.get_by_email(data.email) is not None:
                raise ConflictError(f"Email '{data.email}' already exists", EMAIL_TAKEN_CODE)
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
