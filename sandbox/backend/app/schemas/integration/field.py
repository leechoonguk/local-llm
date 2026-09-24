# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# Classes
# ============================================================

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


#: How a RESPONSE row's `wire_path` is read: a pointer into the decoded body, or
#: one of the three HTML locators a screen needs because it has no pointers.
LocatorKind = Literal["POINTER", "CSS", "LABEL", "REGEX", "SECTION"]


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
    locator_kind: LocatorKind = "POINTER"
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


class IntegrationFieldReadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    direction: FieldDirection
    location: FieldLocation
    key: str
    wire_path: str
    locator_kind: LocatorKind = "POINTER"
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
