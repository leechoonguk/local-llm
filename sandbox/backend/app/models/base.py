# ============================================================
# Imports
# ============================================================

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


# ============================================================
# Constants
# ============================================================

# A parent's collection of child rows: deleted with the parent, and orphans
# deleted when detached. Declared once here because every model file that owns
# children spells the same intent.
CHILD_CASCADE = "all, delete-orphan"

# How wide an actor's name may be. The widest writer is a batch job, which signs
# its rows `batch:<job code>`, and a job is named after the ledger it fills:
# `batch:sync_food_ledger_livestock_item_report_raw_material` is 57 characters.
# Measured 2026-09-15 at 50: the first call log of that job and of two others
# was refused mid-run (StringDataRightTruncationError) after the walk had
# started - the portal was never called, and the run failed with no window.
# 80 leaves room for a ledger name half as long again as today's longest;
# `check-backend-batch` refuses a job code that would not fit.
ACTOR_LENGTH = 80


# ============================================================
# Classes
# ============================================================


class Base(DeclarativeBase):
    pass


class AuditMixin:
    created_by: Mapped[str | None] = mapped_column(String(ACTOR_LENGTH), default=None)
    updated_by: Mapped[str | None] = mapped_column(String(ACTOR_LENGTH), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, Any]:
        """Optimistic locking: a concurrent UPDATE on the same row raises StaleDataError.

        SQLAlchemy adds `WHERE version = <loaded>` to every UPDATE and bumps the
        counter on flush, so a lost update surfaces as a conflict instead of
        silently overwriting the other transaction's work.
        """
        return {"version_id_col": cls.version}
