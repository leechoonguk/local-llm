# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import CheckConstraint, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Classes
# ============================================================


class BatchCheckpoint(Base, AuditMixin):
    """Where one ledger's migration stopped, so the next run continues it.

    A ledger sync walks a paged external operation whose row order is stable
    (measured on I2570: the same window answers the same rows, minutes apart,
    filtered and unfiltered, with no overlap or gap at the page boundary).
    That stability is what makes a **row offset** resumable — and resumable is
    the difference between a 53k-row load that survives being interrupted and
    one that starts over every night.

    `next_range_start` is the first row of the next window, and it cannot be
    derived: counting the ledger is wrong because the feed re-sends the same
    record (measured: 1000 records produced 976 rows), so a row count is
    smaller than the number of rows consumed and would silently skip records.

    **`last_row_key` is what makes the offset trustworthy.** An offset alone is
    a claim about a feed that can be re-ordered under it: delete one record and
    every later row shifts down, so the stored number names a different record
    than the one it was written for, and a walk that trusted it would skip rows
    nobody would notice were missing. The key is the natural identity of the
    last record consumed — whatever identifies a row in *that* feed — so the next
    run can re-read one row and compare instead of assuming.

    It is deliberately **not** the provider's `total_count`. That was tried:
    some operations on this portal report a fixed `1` regardless of the set's
    size, so a count is a field the provider happens to fill, while the rows are
    the thing being read. A checkpoint that trusts a count is only as correct as
    the least careful endpoint it is pointed at.

    **No date bound is stored, on purpose.** The provider offers a 변경일자
    filter, and carrying it here was tried and removed: every I2570 row is
    stamped `2015-01-22` (4000 rows sampled across the whole range), so the
    filter narrows nothing today, while a filter that *did* narrow would hide
    a row inserted later under an older timestamp.
    Keyed by `source_code` — the operation code, one row per external source —
    because the sibling ledgers of this portal resume the same way.
    """

    __tablename__ = "batch_checkpoint"
    __table_args__ = (
        CheckConstraint("next_range_start >= 1", name="ck_batch_checkpoint_next_range_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Nullable because a checkpoint is the batch layer's common place to record
    # where a job stopped, and not every job stops at a *row*: the two purge jobs
    # are bounded by a cutoff they recompute from the clock on every run, so they
    # have no offset to carry. NULL is "this source has no row cursor", which is
    # a different fact from 1 ("start at the first row") — and the column carries
    # no server default for the same reason: a row inserted without an offset
    # would otherwise claim one it never had.
    next_range_start: Mapped[int | None] = mapped_column(Integer, default=None)
    # The natural identity of the last record consumed, as that feed spells it.
    # Opaque here on purpose: one ledger's row is identified by a barcode and a
    # report number, another's by a single code, and the checkpoint has no
    # business knowing which — it stores what the job hands it and hands the same
    # string back. 200 characters holds a composite key without inviting a
    # payload; a value longer than that is a record, not an identity.
    last_row_key: Mapped[str | None] = mapped_column(String(200), default=None)
