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
from app.models.integration.operation import OPERATION_FK, IntegrationOperation
from app.models.integration.secret import SECRET_FK, IntegrationSecret


# ============================================================
# Classes
# ============================================================

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
