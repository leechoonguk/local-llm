# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.integration.operation import (
    IntegrationOperationCreateRequest,
    IntegrationOperationReadResponse,
)
from app.schemas.integration.secret import (
    IntegrationSecretCreateRequest,
    IntegrationSecretReadResponse,
)


# ============================================================
# Classes
# ============================================================

class IntegrationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=2048)
    enabled: bool = True
    secrets: list[IntegrationSecretCreateRequest] = Field(default_factory=list)
    operations: list[IntegrationOperationCreateRequest] = Field(default_factory=list)


class IntegrationCreateRequest(IntegrationBase):
    pass


class IntegrationCreateInternal(IntegrationBase):
    created_by: str


class IntegrationReadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    code: str
    display_name: str
    base_url: str
    enabled: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int
    secrets: list[IntegrationSecretReadResponse]
    operations: list[IntegrationOperationReadResponse]


class IntegrationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    enabled: bool | None = None
    operations: list[IntegrationOperationCreateRequest] | None = None


class IntegrationUpdateInternal(IntegrationUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================

def to_read(provider: object) -> IntegrationReadResponse:
    return IntegrationReadResponse.model_validate(provider)


def to_read_list(providers: Sequence[object]) -> list[IntegrationReadResponse]:
    return [to_read(provider) for provider in providers]
