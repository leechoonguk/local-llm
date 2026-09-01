# ============================================================
# Imports
# ============================================================

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.refresh import Refresh


# ============================================================
# Classes
# ============================================================


class RefreshBase(BaseModel):
    """Whose session a token stands for.

    Neither the secret nor its deadline is here. The secret exists once, in the
    answer to the request that minted it, and the deadline is the service's to
    set — a caller that could choose `expires_at` could choose a token that
    never expires.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: UUID


class RefreshCreateRequest(RefreshBase):
    pass


class RefreshCreateInternal(RefreshBase):
    token_hash: str
    expires_at: datetime
    created_by: str


class RefreshReadResponse(RefreshBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    expires_at: datetime
    revoked_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class RefreshUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revoked_at: datetime | None = None


class RefreshUpdateInternal(RefreshUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================


def to_read(refresh: Refresh) -> RefreshReadResponse:
    return RefreshReadResponse.model_validate(refresh)


def to_read_list(refreshes: list[Refresh]) -> list[RefreshReadResponse]:
    return [RefreshReadResponse.model_validate(r) for r in refreshes]
