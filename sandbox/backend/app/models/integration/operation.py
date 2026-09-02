# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any
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

from app.models.base import CHILD_CASCADE, AuditMixin, Base
from app.models.integration.provider import PROVIDER_FK, Integration


if TYPE_CHECKING:
    from app.models.integration.call import IntegrationCall
    from app.models.integration.field import IntegrationField


# ============================================================
# Constants
# ============================================================

OPERATION_FK = "integration_operation.id"


# ============================================================
# Classes
# ============================================================


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
        back_populates="operation",
        cascade=CHILD_CASCADE,
        passive_deletes=True,
        lazy="raise_on_sql",
    )
    calls: Mapped[list[IntegrationCall]] = relationship(
        back_populates="operation",
        lazy="raise_on_sql",
    )
