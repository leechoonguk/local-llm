# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Constants
# ============================================================

SCHEDULE_FK = "batch_schedule.id"


# ============================================================
# Classes
# ============================================================


class BatchRun(Base, AuditMixin):
    """One execution of a scheduled job: when it ran, and how it ended.

    The four endings are different facts and the row keeps them apart. A job
    that raised is not a job an operator stopped, and neither is a job whose
    process died — that last one has no writer at all, which is why
    `INTERRUPTED` exists: the next startup sweeps whatever is still `RUNNING`,
    because nothing else can. Without it a killed run stays `RUNNING` forever
    and every dashboard reads "still going".

    `batch_id` is `SET NULL` and `code` is stored beside it: the log outlives
    the schedule it ran, the same contract `integration_call` keeps with its
    operation. Deleting a schedule must not erase what it did last month.

    `result` is what the job function returned — the count it reports. The
    steps carry their own numbers; the two answer different questions ("what
    did this run accomplish" versus "where did it spend its windows"), so
    neither is derived from the other.
    """

    __tablename__ = "batch_run"
    __table_args__ = (
        Index("ix_batch_run_code_started_at", "code", "started_at"),
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'STOPPED', 'INTERRUPTED', 'SKIPPED')",
            name="ck_batch_run_status",
        ),
        CheckConstraint("trigger IN ('CRON', 'MANUAL')", name="ck_batch_run_trigger"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_batch_run_duration"),
        # A finished run has a finishing time, and a running one has none. The
        # pair is the whole state machine, so the database holds it rather than
        # trusting every writer to.
        CheckConstraint(
            "(status = 'RUNNING') = (finished_at IS NULL)",
            name="ck_batch_run_finished_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey(SCHEDULE_FK, ondelete="SET NULL"), index=True, default=None
    )
    code: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    trigger: Mapped[str] = mapped_column(String(8))
    triggered_by: Mapped[str] = mapped_column(String(50))
    stopped_by: Mapped[str | None] = mapped_column(String(50), default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    result: Mapped[int | None] = mapped_column(Integer, default=None)
    error_code: Mapped[str | None] = mapped_column(String(64), default=None)
    error_detail: Mapped[str | None] = mapped_column(String(512), default=None)
