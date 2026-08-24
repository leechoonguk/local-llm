# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base


# ============================================================
# Constants
# ============================================================

PROVIDER_FK = "integration_provider.id"
OPERATION_FK = "integration_operation.id"
SECRET_FK = "integration_secret.id"
CHILD_CASCADE = "all, delete-orphan"


# ============================================================
# Classes
# ============================================================

class Integration(Base, AuditMixin):
    __tablename__ = "integration_provider"
    __table_args__ = (UniqueConstraint("code", name="uq_integration_provider_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str] = mapped_column(String(2048))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    operations: Mapped[list[IntegrationOperation]] = relationship(
        back_populates="provider", cascade=CHILD_CASCADE, passive_deletes=True,
        lazy="raise_on_sql",
    )
    secrets: Mapped[list[IntegrationSecret]] = relationship(
        back_populates="provider", cascade=CHILD_CASCADE, passive_deletes=True,
        lazy="raise_on_sql",
    )


class IntegrationSecret(Base, AuditMixin):
    """A named credential owned by one provider.

    Secrets live here rather than on the field rows that consume them: a key is
    rotated in one place, survives a full replacement of an operation's fields,
    and is stored once no matter how many operations send it.
    """

    __tablename__ = "integration_secret"
    __table_args__ = (
        UniqueConstraint("provider_id", "name", name="uq_integration_secret_provider_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey(PROVIDER_FK, ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(String(512), default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    provider: Mapped[Integration] = relationship(
        back_populates="secrets",
        lazy="raise_on_sql",
    )
    fields: Mapped[list[IntegrationField]] = relationship(
        back_populates="secret",
        lazy="raise_on_sql",
    )


class IntegrationOperation(Base, AuditMixin):
    """One callable endpoint: transport settings plus its response contract.

    The canonical payload is always built from this operation's RESPONSE field rows.
    `response_root` decides what those rows are pointed at:

    - absent — absolute pointers, one canonical record;
    - present — a pointer at a page (array), and each row's `wire_path` is relative
      to one element, so one row per provider column maps every record the page
      carries. This is the shape a paging API takes: the window the caller asked for
      comes back whole, and every column keeps its key, type and description.

    RESPONSE field rows always validate the response and always build the payload;
    there is no mode in which they are decoration.
    """

    __tablename__ = "integration_operation"
    __table_args__ = (
        UniqueConstraint("provider_id", "code", name="uq_integration_operation_provider_code"),
        CheckConstraint("connect_timeout_ms > 0", name="ck_integration_operation_connect_timeout"),
        CheckConstraint(
            "read_timeout_ms >= connect_timeout_ms", name="ck_integration_operation_read_timeout"
        ),
        CheckConstraint("max_retries >= 0", name="ck_integration_operation_max_retries"),
        CheckConstraint("retry_base_ms > 0", name="ck_integration_operation_retry_base"),
        CheckConstraint("retry_max_ms >= retry_base_ms", name="ck_integration_operation_retry_max"),
        CheckConstraint(
            "response_format IN ('JSON', 'XML')", name="ck_integration_operation_response_format"
        ),
        CheckConstraint(
            "response_root IS NULL OR response_root LIKE '/%'",
            name="ck_integration_operation_response_root",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey(PROVIDER_FK, ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(10))
    path_template: Mapped[str] = mapped_column(String(2048))
    request_media_type: Mapped[str | None] = mapped_column(String(120), default=None)
    response_format: Mapped[str] = mapped_column(String(8), default="JSON", server_default="JSON")
    response_root: Mapped[str | None] = mapped_column(String(512), default=None)
    connect_timeout_ms: Mapped[int] = mapped_column(Integer)
    read_timeout_ms: Mapped[int] = mapped_column(Integer)
    max_retries: Mapped[int] = mapped_column(Integer)
    retry_base_ms: Mapped[int] = mapped_column(Integer)
    retry_max_ms: Mapped[int] = mapped_column(Integer)
    idempotent: Mapped[bool] = mapped_column(Boolean)
    request_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    provider: Mapped[Integration] = relationship(
        back_populates="operations",
        lazy="raise_on_sql",
    )
    fields: Mapped[list[IntegrationField]] = relationship(
        back_populates="operation", cascade=CHILD_CASCADE, passive_deletes=True,
        lazy="raise_on_sql",
    )


class IntegrationField(Base, AuditMixin):
    """One wire field of an operation, inbound or outbound.

    `direction` selects the half of the contract a row describes, replacing the
    former request-field / response-header / response-field tables:

    - `REQUEST` — `key` is the caller-facing input name, `wire_path` is where it
      goes on the wire, and `value_source` says where the value comes from.
    - `RESPONSE` — `key` is the canonical result key and `wire_path` is the JSON
      Pointer it is read from.
    """

    __tablename__ = "integration_field"
    __table_args__ = (
        UniqueConstraint("operation_id", "direction", "key", name="uq_integration_field_key"),
        UniqueConstraint(
            "operation_id", "direction", "location", "wire_path", name="uq_integration_field_wire"
        ),
        CheckConstraint("ordinal >= 0", name="ck_integration_field_ordinal"),
        CheckConstraint(
            "direction IN ('REQUEST', 'RESPONSE')", name="ck_integration_field_direction"
        ),
        CheckConstraint(
            "location IN ('PATH', 'PATH_QUERY', 'QUERY', 'HEADER', 'BODY', 'ENVELOPE')",
            name="ck_integration_field_location",
        ),
        CheckConstraint(
            "value_type IN ('STRING', 'INTEGER', 'NUMBER', 'BOOLEAN', 'DATE', 'DATETIME', "
            "'JSON', 'EPOCH_SECONDS', 'HTTP_DATE', 'DURATION_SECONDS')",
            name="ck_integration_field_value_type",
        ),
        # Header-only wire encodings never apply to a body or query field.
        CheckConstraint(
            "value_type NOT IN ('EPOCH_SECONDS', 'HTTP_DATE', 'DURATION_SECONDS') "
            "OR location = 'HEADER'",
            name="ck_integration_field_header_value_type",
        ),
        # Outbound rows declare where their value comes from; inbound rows never do.
        CheckConstraint(
            "(direction = 'REQUEST' AND value_source IS NOT NULL) "
            "OR (direction = 'RESPONSE' AND value_source IS NULL)",
            name="ck_integration_field_value_source_direction",
        ),
        CheckConstraint(
            "value_source IS NULL "
            "OR value_source IN ('CALLER', 'LITERAL', 'SECRET', 'CONTEXT')",
            name="ck_integration_field_value_source",
        ),
        # A secret reference is exactly the SECRET source, never a stray FK.
        CheckConstraint(
            "(value_source = 'SECRET' AND secret_id IS NOT NULL) "
            "OR (value_source IS DISTINCT FROM 'SECRET' AND secret_id IS NULL)",
            name="ck_integration_field_secret",
        ),
        # A literal field with no value would send nothing.
        CheckConstraint(
            "value_source IS DISTINCT FROM 'LITERAL' OR value IS NOT NULL",
            name="ck_integration_field_literal_value",
        ),
        # A matched value is one the provider sends: a response header, or a verdict
        # in the body wrapper that decides whether the answer counts at all.
        CheckConstraint(
            "(match_mode IS NULL AND expected_values IS NULL) "
            "OR (direction = 'RESPONSE' AND location IN ('HEADER', 'ENVELOPE'))",
            name="ck_integration_field_match_direction",
        ),
        CheckConstraint(
            "match_mode IS NULL OR match_mode IN ('IGNORE', 'PRESENT', 'EXACT', 'ONE_OF')",
            name="ck_integration_field_match_mode",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    operation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey(OPERATION_FK, ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(8))
    location: Mapped[str] = mapped_column(String(10))
    key: Mapped[str] = mapped_column(String(128))
    wire_path: Mapped[str] = mapped_column(String(512))
    value_source: Mapped[str | None] = mapped_column(String(16), default=None)
    value: Mapped[Any | None] = mapped_column(JSON(none_as_null=True), default=None)
    secret_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey(SECRET_FK, ondelete="RESTRICT"), index=True, default=None
    )
    value_type: Mapped[str] = mapped_column(String(20))
    format: Mapped[str | None] = mapped_column(String(64), default=None)
    required: Mapped[bool] = mapped_column(Boolean)
    description: Mapped[str | None] = mapped_column(String(512), default=None)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    match_mode: Mapped[str | None] = mapped_column(String(16), default=None)
    expected_values: Mapped[list[str] | None] = mapped_column(
        JSON(none_as_null=True), default=None
    )
    operation: Mapped[IntegrationOperation] = relationship(
        back_populates="fields",
        lazy="raise_on_sql",
    )
    secret: Mapped[IntegrationSecret | None] = relationship(
        back_populates="fields",
        lazy="raise_on_sql",
    )

    @property
    def secret_name(self) -> str | None:
        """The referenced secret's name — read models expose this, never the value."""
        return None if self.secret is None else self.secret.name
