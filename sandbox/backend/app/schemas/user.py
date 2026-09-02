# ============================================================
# Imports
# ============================================================

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import User


# ============================================================
# Constants
# ============================================================

USERNAME_MIN_LENGTH = 1

USERNAME_MAX_LENGTH = 50

EMAIL_MAX_LENGTH = 255

PASSWORD_MIN_LENGTH = 8

PASSWORD_MAX_LENGTH = 128

# Deliberately loose: one `@`, a dot in the domain, no spaces. Anything stricter
# rejects addresses that exist, and `email-validator` is not a dependency here.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# ============================================================
# Classes
# ============================================================


class UserBase(BaseModel):
    """Field names shared by every direction - deliberately without rules.

    A read model must never re-validate stored data. When these constraints
    lived here, one row written before they existed (`not-an-email`) made
    `GET /user/` answer 500 for every caller: the list could not be serialised
    at all. Input rules belong on input models.
    """

    model_config = ConfigDict(extra="forbid")

    username: str
    email: str


class UserCreateRequest(UserBase):
    """What a client may send. Lengths mirror the columns (`String(50)` /
    `String(255)`), so a value the column cannot hold fails as a 422 rather
    than a database error. The email shape and the password minimum used to
    live only in the browser form, so `curl` stored `not-an-email` with a
    one-character password and got HTTP 201 (measured).
    """

    username: str = Field(min_length=USERNAME_MIN_LENGTH, max_length=USERNAME_MAX_LENGTH)
    email: str = Field(max_length=EMAIL_MAX_LENGTH, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


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

    username: str | None = Field(
        default=None,
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
    )
    email: str | None = Field(
        default=None,
        max_length=EMAIL_MAX_LENGTH,
        pattern=EMAIL_PATTERN,
    )
    password: str | None = Field(
        default=None,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
    )


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
