# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.integration.operation import OPERATION_FK, IntegrationOperation


# ============================================================
# Classes
# ============================================================


class IntegrationCall(Base, AuditMixin):
    """One executed external call: what left this process, and what came back.

    The log outlives the configuration it used. `operation_id` is `SET NULL` and
    the provider and operation codes are stored as strings, because a `_replace_`
    revision deletes and re-inserts the operation row - a log that disappeared
    with its configuration could not answer what we sent last month.

    Nothing here is written raw: the URL, the headers and the bodies pass through
    the client's secret scrubber first, since these providers carry the credential
    as a path segment and echo the request back.
    """

    __tablename__ = "integration_call"
    __table_args__ = (
        Index("ix_integration_call_provider_code_created_at", "provider_code", "created_at"),
        CheckConstraint(
            "method IN ('GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE')",
            name="ck_integration_call_method",
        ),
        CheckConstraint(
            "outcome IN ('SUCCESS', 'REFUSED', 'TIMEOUT', 'UNREACHABLE', 'RATE_LIMITED')",
            name="ck_integration_call_outcome",
        ),
        CheckConstraint("duration_ms >= 0", name="ck_integration_call_duration"),
        CheckConstraint("attempts >= 1", name="ck_integration_call_attempts"),
        CheckConstraint(
            "status_code IS NULL OR (status_code BETWEEN 100 AND 599)",
            name="ck_integration_call_status_code",
        ),
        # Nothing answered means no status code; an answer means there is one.
        CheckConstraint(
            "(outcome IN ('TIMEOUT', 'UNREACHABLE') AND status_code IS NULL) "
            "OR (outcome NOT IN ('TIMEOUT', 'UNREACHABLE') AND status_code IS NOT NULL)",
            name="ck_integration_call_answered",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    operation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey(OPERATION_FK, ondelete="SET NULL"), index=True, default=None
    )
    provider_code: Mapped[str] = mapped_column(String(64))
    operation_code: Mapped[str] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(10))
    url: Mapped[str] = mapped_column(String(2048))
    request_headers: Mapped[dict[str, Any]] = mapped_column(JSON)
    request_body: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(none_as_null=True), default=None
    )
    status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    response_headers: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(none_as_null=True), default=None
    )
    # Text, not a bounded String: a provider's page is XML or JSON of
    # unpredictable size. The client truncates before it reaches here, so the
    # bound is one constant instead of a column length nobody reads.
    response_body: Mapped[str | None] = mapped_column(Text, default=None)
    outcome: Mapped[str] = mapped_column(String(16))
    duration_ms: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    error_code: Mapped[str | None] = mapped_column(String(64), default=None)
    error_detail: Mapped[str | None] = mapped_column(String(512), default=None)
    operation: Mapped[IntegrationOperation | None] = relationship(
        back_populates="calls",
        lazy="raise_on_sql",
    )
