# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# Classes
# ============================================================


class IntegrationSecretCreateRequest(BaseModel):
    """A named provider credential. The value is write-only."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=2048)
    description: str | None = Field(default=None, max_length=512)
    enabled: bool = True
    # Secrets of one provider sharing a group are interchangeable - the client
    # sends whichever member is not spent. Absent: this secret stands alone.
    rotation_group: str | None = Field(default=None, min_length=1, max_length=64)


class IntegrationSecretReadResponse(BaseModel):
    """Secret metadata without the secret. `value` is never echoed."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    name: str
    description: str | None = None
    enabled: bool
    rotation_group: str | None = None
    exhausted_until: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class IntegrationSecretUpdateRequest(BaseModel):
    """A partial update of one named credential.

    An omitted `value` keeps the stored one: rotating a key and renaming its
    description are separate intents, and a client that cannot read the value back
    could not resend it anyway.
    """

    model_config = ConfigDict(extra="forbid")

    value: str | None = Field(default=None, min_length=1, max_length=2048)
    description: str | None = Field(default=None, max_length=512)
    enabled: bool | None = None
    rotation_group: str | None = Field(default=None, min_length=1, max_length=64)
