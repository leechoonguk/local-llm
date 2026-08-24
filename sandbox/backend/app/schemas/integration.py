# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


JsonObject = dict[str, object]
FieldDirection = Literal["REQUEST", "RESPONSE"]
FieldLocation = Literal["PATH", "PATH_QUERY", "QUERY", "HEADER", "BODY", "ENVELOPE"]
RequestValueSource = Literal["CALLER", "LITERAL", "SECRET", "CONTEXT"]
ValueType = Literal[
    "STRING",
    "INTEGER",
    "NUMBER",
    "BOOLEAN",
    "DATE",
    "DATETIME",
    "JSON",
    "EPOCH_SECONDS",
    "HTTP_DATE",
    "DURATION_SECONDS",
]
HeaderMatchMode = Literal["IGNORE", "PRESENT", "EXACT", "ONE_OF"]
ResponseFormat = Literal["JSON", "XML"]


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


class IntegrationFieldCreateRequest(BaseModel):
    """One wire field of an operation, inbound or outbound.

    `direction` selects which half of the contract the row describes: REQUEST
    rows carry a `value_source`, RESPONSE rows never do.
    """

    model_config = ConfigDict(extra="forbid")

    direction: FieldDirection
    location: FieldLocation
    key: str = Field(min_length=1, max_length=128)
    wire_path: str = Field(min_length=1, max_length=512)
    value_source: RequestValueSource | None = None
    value: object | None = None
    secret_name: str | None = Field(default=None, max_length=64)
    value_type: ValueType
    format: str | None = Field(default=None, max_length=64)
    required: bool
    description: str | None = Field(default=None, max_length=512)
    sensitive: bool = False
    ordinal: int = Field(default=0, ge=0)
    enabled: bool = True
    match_mode: HeaderMatchMode | None = None
    expected_values: list[str] | None = None


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
    enabled: bool = True
    fields: list[IntegrationFieldCreateRequest] = Field(default_factory=list)


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


class IntegrationSecretReadResponse(BaseModel):
    """Secret metadata without the secret. `value` is never echoed."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    name: str
    description: str | None = None
    enabled: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class IntegrationFieldReadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    direction: FieldDirection
    location: FieldLocation
    key: str
    wire_path: str
    value_source: RequestValueSource | None = None
    value: object | None = None
    secret_name: str | None = None
    value_type: ValueType
    format: str | None = None
    required: bool
    description: str | None = None
    sensitive: bool
    ordinal: int
    enabled: bool
    match_mode: HeaderMatchMode | None = None
    expected_values: list[str] | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


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
    enabled: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int
    fields: list[IntegrationFieldReadResponse]


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

def to_read(provider: object) -> IntegrationReadResponse:
    return IntegrationReadResponse.model_validate(provider)


def to_read_list(providers: Sequence[object]) -> list[IntegrationReadResponse]:
    return [to_read(provider) for provider in providers]
