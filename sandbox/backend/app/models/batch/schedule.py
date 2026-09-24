# ============================================================
# Imports
# ============================================================

import uuid
from uuid import uuid4

from sqlalchemy import Boolean, String, Uuid, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Classes
# ============================================================


class BatchSchedule(Base, AuditMixin):
    """One scheduled batch job: which code runs, when, and whether it runs at all.

    The row owns the schedule; the repository's Python owns the work. `code`
    names a callable registered in `app.core.scheduler.BATCH_JOBS`, so a job is
    added by writing one function and one row — never by editing the lifespan.
    It is also the row's only name: a `name` column stood here until
    2026-09-22, and on all 33 rows it was the code restyled
    (`sync_food_ledger_recall` → "Sync food_ledger_recall"), so it read like a
    second identity while carrying no fact the code did not.

    `code` is deliberately **not** unique: the same job may be scheduled twice
    (a nightly full pass and a midday partial one), and the scheduler is keyed
    on the row id, which is unique already.

    `enabled` is **activation**: whether the clock starts this job at all. It is
    a column rather than a deleted row because deactivating must not lose the
    cron — an operator who switches a job off at 02:00 switches the same
    schedule back on, not one retyped from memory. Interrupting a run that is
    already in flight is a different verb (`POST /batch/{id}/run`), and a
    deactivated row can still be run by hand.
    """

    __tablename__ = "batch_schedule"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), index=True)
    cron: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
