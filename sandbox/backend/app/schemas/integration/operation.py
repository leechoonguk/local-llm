# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.integration.field import (
    IntegrationFieldCreateRequest,
    IntegrationFieldReadResponse,
)


# ============================================================
# Classes
# ============================================================

JsonObject = dict[str, object]


ResponseFormat = Literal["JSON", "XML"]


class IntegrationOperationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    method: Literal["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"]
    path_template: str = Field(min_length=1, max_length=2048)
    request_media_type: str | None = Field(default=None, max_length=120)
    response_format: ResponseFormat = "JSON"
    response_root: str | None = Field(default=None, max_length=512)
    connect_timeout_ms: int = Field(gt=0)
    read_timeout_ms: int = Field(gt=0)
    max_retries: int = Field(ge=0)
    retry_base_ms: int = Field(gt=0)
    retry_max_ms: int = Field(gt=0)
    idempotent: bool
    request_schema: JsonObject | None = None
    # Envelope values that mean "not this key right now", each with the seconds
    # the key sits out: the client tries the next member of the key's rotation
    # group before it raises. Empty for a provider without per-key state.
    quota_codes: dict[str, int] = Field(default_factory=dict, max_length=16)
    enabled: bool = True
    fields: list[IntegrationFieldCreateRequest] = Field(default_factory=list)


class IntegrationOperationReadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    code: str
    method: str
    path_template: str
    request_media_type: str | None = None
    response_format: ResponseFormat = "JSON"
    response_root: str | None = None
    connect_timeout_ms: int
    read_timeout_ms: int
    max_retries: int
    retry_base_ms: int
    retry_max_ms: int
    idempotent: bool
    request_schema: JsonObject | None = None
    quota_codes: dict[str, int]
    enabled: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int
    fields: list[IntegrationFieldReadResponse]


class IntegrationExecuteRequest(BaseModel):
    """Caller-supplied values for CALLER-sourced request fields."""

    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, object] = Field(default_factory=dict)


class IntegrationExecuteResponse(BaseModel):
    """Canonical result of one configured external API execution."""

    model_config = ConfigDict(extra="forbid")

    canonical_payload: dict[str, object] | list[object]
    metadata: dict[str, object]
    status_code: int


# ============================================================
# Functions
# ============================================================
