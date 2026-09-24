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

    `response_format = 'CSV'` is a **file**: one request answers the whole feed
    as a gzip CSV, and the rows are read off it in chunks of `page_size` by
    `IntegrationClient.stream` rather than windowed by a paging family. The
    RESPONSE rows are the same rows - a pointer `/PRDTNM` reads the column of
    that name - and there is no envelope, because the portal states a file's
    refusal as an HTTP 429 (measured 2026-09-19: `INFO-500` and `INFO-330`
    both arrive as 429 with an XML body). `response_root` is NULL: the file
    is the page.
    """

    __tablename__ = "integration_operation"
    __table_args__ = (
        UniqueConstraint("provider_id", "code", name="uq_integration_operation_provider_code"),
        CheckConstraint("connect_timeout_ms > 0", name="ck_integration_operation_connect_timeout"),
        CheckConstraint(
            "read_timeout_ms >= connect_timeout_ms", name="ck_integration_operation_read_timeout"
        ),
        CheckConstraint("max_retries >= 0", name="ck_integration_operation_max_retries"),
        CheckConstraint("page_size > 0", name="ck_integration_operation_page_size"),
        # A coordinate and the values it takes are one fact, stated twice or not
        # at all: a key with no values has nothing to ask for, and values with no
        # key have nothing to be put in.
        CheckConstraint(
            "(segment_key IS NULL) = (segment_values IS NULL)",
            name="ck_integration_operation_segment",
        ),
        CheckConstraint(
            "segment_values IS NULL OR json_array_length(segment_values) > 0",
            name="ck_integration_operation_segment_values",
        ),
        CheckConstraint("retry_base_ms > 0", name="ck_integration_operation_retry_base"),
        CheckConstraint("retry_max_ms >= retry_base_ms", name="ck_integration_operation_retry_max"),
        CheckConstraint(
            "response_format IN ('JSON', 'XML', 'HTML', 'CSV')",
            name="ck_integration_operation_response_format",
        ),
        # What the root is depends on the format, because the two are the same
        # decision from two decoders: a JSON/XML page is an RFC 6901 pointer, and an
        # HTML page is the CSS selector for its rows (`table.board_list tbody tr`).
        CheckConstraint(
            "response_root IS NULL OR response_format = 'HTML' OR response_root LIKE '/%'",
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
    # How many records one window of this operation asks for - the service's own
    # measured ceiling, not the job's. It was a job constant until 2026-09-14,
    # when one gateway's narrowest service (B553748, 100) was making its widest
    # (IprtFoodPrdtKoreanLabelingText, 500) walk 10,878 windows instead of 2,176;
    # and because a window's cost grows with its page number on that gateway
    # (measured: 363 ms at page 1-200, 1,441 ms at 1,400), the narrow width cost
    # 13 hours against 66 minutes for the same rows.
    page_size: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    # Which caller input addresses this feed, when the service publishes one set
    # per coordinate instead of one flat sequence (보고년도 on 생산실적). It is not a
    # filter: a walk asks every coordinate in turn and the pages of all of them
    # are one pass. It is a cost decision - this gateway charges for the OFFSET it
    # scans, so a walk's cost grows with the square of its windows, and starting
    # the offset over per coordinate is what keeps a large feed walkable.
    segment_key: Mapped[str | None] = mapped_column(String(64), default=None)
    # The values that coordinate takes, as the service publishes them. They are
    # listed rather than generated: what a coordinate *is* - a year, a region, a
    # category - is knowledge only this row has, and code that generated
    # candidates would have to know. The walk asks each one for a single row
    # first and walks the ones that answer, so a value the service does not
    # publish yet costs one window and is skipped.
    # `none_as_null` because the CHECK reads SQL NULL: without it a flat feed
    # stores the JSON literal `null`, which is not NULL, and the pairing
    # constraint refuses every unsegmented operation.
    segment_values: Mapped[list[str] | None] = mapped_column(JSON(none_as_null=True), default=None)
    connect_timeout_ms: Mapped[int] = mapped_column(Integer)
    read_timeout_ms: Mapped[int] = mapped_column(Integer)
    max_retries: Mapped[int] = mapped_column(Integer)
    retry_base_ms: Mapped[int] = mapped_column(Integer)
    retry_max_ms: Mapped[int] = mapped_column(Integer)
    idempotent: Mapped[bool] = mapped_column(Boolean)
    request_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    # Envelope values that mean "not this credential right now", not "this
    # answer is wrong", each with how long the key sits out in seconds: the
    # client tries the next key of the pool before it raises. Measured on
    # mfds-food-safety-korea: INFO-320 (hour's quota spent) recovers within
    # the hour, INFO-500 (key busy - "잠시 후에 다시") within seconds. Empty
    # when the provider has no per-key state. Disjoint from the ENVELOPE row's
    # accepted values by construction (service and check refuse the overlap).
    quota_codes: Mapped[dict[str, int]] = mapped_column(JSON, default=dict, server_default="{}")
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
