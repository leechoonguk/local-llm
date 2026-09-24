# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal
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


#: How the portal answers, and therefore which decoder reads it: an API that
#: returns JSON/XML, or a public screen that returns HTML behind a session cookie.
Transport = Literal["HTTP_JSON", "HTML_FORM"]


class IntegrationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=2048)
    transport: Transport = "HTTP_JSON"
    bootstrap_path: str | None = Field(default=None, max_length=512)
    min_interval_ms: int = Field(default=0, ge=0)
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
    transport: Transport = "HTTP_JSON"
    bootstrap_path: str | None = None
    min_interval_ms: int = 0
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
    transport: Transport | None = None
    bootstrap_path: str | None = Field(default=None, max_length=512)
    min_interval_ms: int | None = Field(default=None, ge=0)
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
