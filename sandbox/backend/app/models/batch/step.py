# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Constants
# ============================================================

RUN_FK = "batch_run.id"

CALL_FK = "integration_call.id"


# ============================================================
# Classes
# ============================================================


class BatchStep(Base, AuditMixin):
    """One unit of work inside a run — for a paging job, one window.

    A run says the night failed; a step says which window it failed on and
    what that window had already imported. That is the difference between
    "the sync is broken" and "row 41,000 of the provider's set is".

    `integration_call_id` is the join that makes the log worth keeping: from a
    failed step to the exact request and the provider's own answer, scrubbed
    and stored (`integration_call`). Nullable and `SET NULL` — a step may fail
    before any call leaves, and the call log has its own retention.

    Rows are written **after** the unit ends, so a step is `SUCCEEDED` or
    `FAILED` and never `RUNNING`. A unit interrupted mid-flight leaves no row,
    which is honest: it did not finish, and the run carries that verdict.
    """

    __tablename__ = "batch_step"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_batch_step_run_id_sequence"),
        CheckConstraint("status IN ('SUCCEEDED', 'FAILED')", name="ck_batch_step_status"),
        CheckConstraint("sequence >= 1", name="ck_batch_step_sequence"),
        CheckConstraint("duration_ms >= 0", name="ck_batch_step_duration"),
        CheckConstraint(
            "range_start IS NULL OR range_start >= 1",
            name="ck_batch_step_range_start",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey(RUN_FK, ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    range_start: Mapped[int | None] = mapped_column(Integer, default=None)
    range_end: Mapped[int | None] = mapped_column(Integer, default=None)
    received: Mapped[int | None] = mapped_column(Integer, default=None)
    written: Mapped[int | None] = mapped_column(Integer, default=None)
    duration_ms: Mapped[int] = mapped_column(Integer)
    integration_call_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey(CALL_FK, ondelete="SET NULL"), index=True, default=None
    )
    error_code: Mapped[str | None] = mapped_column(String(64), default=None)
    error_detail: Mapped[str | None] = mapped_column(String(512), default=None)
