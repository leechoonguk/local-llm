# ============================================================
# Imports
# ============================================================

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.user import User


# ============================================================
# Classes
# ============================================================

class UserBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    email: str


class UserCreateRequest(UserBase):
    password: str


class UserCreateInternal(UserBase):
    hashed_password: str
    created_by: str


class UserReadResponse(UserBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = None
    email: str | None = None
    password: str | None = None


class UserUpdateInternal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = None
    email: str | None = None
    hashed_password: str | None = None
    updated_by: str


# ============================================================
# Functions
# ============================================================

def to_read(user: User) -> UserReadResponse:
    return UserReadResponse.model_validate(user)


def to_read_list(users: list[User]) -> list[UserReadResponse]:
    return [UserReadResponse.model_validate(u) for u in users]
