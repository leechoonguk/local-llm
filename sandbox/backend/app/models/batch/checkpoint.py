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

    A ledger sync walks a paged external operation whose order is stable
    (measured on I2570: the same window answers the same rows, minutes apart,
    filtered and unfiltered, with no overlap or gap at the page boundary).
    That stability is what makes a position resumable — and resumable is the
    difference between a 300k-record load that survives being interrupted and
    one that starts over every night.

    **`resume_position` is a position in the unit its own feed pages by**, and
    the two units in this codebase are not interchangeable:

    | Paging family | What the number is | Ledger |
    |---|---|---|
    | RANGE (`range_start`/`range_end`) | first **row** of the next window | raw material |
    | PAGE (`page_no`/`num_of_rows`) | the **page** the last run imported | nutrition |

    The column stays one column because the checkpoint's job is the same either
    way — carry a number and the evidence that it still points where it did —
    and because a second nullable column per family would let a row claim both.
    It was called `next_range_start` while only row walks existed; the page
    ledger then stored page numbers in a column whose name said rows, which is
    the kind of lie a reader only finds by reading the job.

    It cannot be derived: counting the ledger is wrong because the feed re-sends
    the same record (measured: 1000 records produced 976 rows), so a row count is
    smaller than the number of rows consumed and would silently skip records.

    **`resume_key` is what makes the position trustworthy.** A position alone is
    a claim about a feed that can be re-ordered under it: delete one record and
    every later row shifts down, so the stored number names a different record
    than the one it was written for, and a walk that trusted it would skip rows
    nobody would notice were missing. The key is the natural identity of the
    record that proves the position, so the next run re-reads and compares
    instead of assuming.

    **Which record proves it is the job's decision, not this table's.** A row
    walk stores the last record it consumed and re-reads that one row. A page
    walk stores the *first* record of the page it will resume on: new records are
    appended to the last page, so its last record changes on any ordinary night,
    and anchoring there would read every normal night as a re-ordered feed and
    re-import the whole set.

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
        CheckConstraint("resume_position >= 1", name="ck_batch_checkpoint_resume_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Nullable because a checkpoint is the batch layer's common place to record
    # where a job stopped, and not every job stops at a position: the two purge jobs
    # are bounded by a cutoff they recompute from the clock on every run, so they
    # have no position to carry. NULL is "this source has no cursor", which is a
    # different fact from 1 ("start at the first row or page") — and the column
    # carries no server default for the same reason: a row inserted without a
    # position would otherwise claim one it never had.
    resume_position: Mapped[int | None] = mapped_column(Integer, default=None)
    # The natural identity of the record that proves the position, as that feed
    # spells it. Opaque here on purpose: one ledger's row is identified by a
    # barcode and a report number, another's by a single code, and the checkpoint
    # has no business knowing which — it stores what the job hands it and hands
    # the same string back. 200 characters holds a composite key without inviting a
    # payload; a value longer than that is a record, not an identity.
    resume_key: Mapped[str | None] = mapped_column(String(200), default=None)
