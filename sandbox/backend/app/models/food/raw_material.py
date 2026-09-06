# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Classes
# ============================================================


class FoodRawMaterial(Base, AuditMixin):
    """식품 원재료 원장 — our own copy of the I2520 records, one row per material.

    The second ledger of the `food_*` family, and it is a sibling rather than a
    section of the first: I2570 keys on 바코드번호 and I2520 on 원재료코드, and
    the two answer different columns entirely. Folding them together would need
    a nullable column per foreign concept and a `source` discriminator on every
    query — a JSON blob wearing a schema (rule://backend-table-design, 1NF).

    **The natural key is one column here, not two.** `raw_material_code`
    (RAWMTRL_CD) identifies a material across the whole portal, which is why the
    barcode ledger's `(barcode_no, report_no)` pair has no analogue: the upsert
    target is the code alone, and the provider re-sends the same record on every
    overlapping window.

    `source_updated_at` is the provider's own 최종수정일시, which makes this
    table its own sync cursor the same way the barcode ledger is: a completed
    pass hands its maximum to the next as `changed_from`. It is nullable because
    the provider leaves the column empty on sparse records.
    """

    __tablename__ = "food_raw_material"
    __table_args__ = (Index("ix_food_raw_material_source_updated_at", "source_updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    # Unique on the column itself: the identity is one code, so the constraint
    # is the column's own rather than a table-level pair.
    raw_material_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    # Provider free text: 200 rather than the usual 120 for a display name,
    # because a rejected INSERT would fail the whole page for one long name.
    representative_raw_material_name: Mapped[str | None] = mapped_column(String(200), default=None)
    # 이명·영문명·학명 are synonym *lists*, not names: the portal joins every
    # alias it knows into one comma-separated string, and its length is an
    # editorial choice nobody publishes. Measured over the whole feed
    # (2026-09-05, 43,609 records): alias 1130, scientific 311, english 272 —
    # against maxima of 94/225/242 in the first 3000 rows. Two bounds were tried
    # and both were exceeded further down the feed, each costing a whole page,
    # because a rejected INSERT fails the window rather than the row. `Text`
    # stores identically to `String` in Postgres, so the bound was buying
    # nothing but the outage.
    raw_material_alias: Mapped[str | None] = mapped_column(Text, default=None)
    english_name: Mapped[str | None] = mapped_column(Text, default=None)
    scientific_name: Mapped[str | None] = mapped_column(Text, default=None)
    raw_material_large_class: Mapped[str | None] = mapped_column(String(120), default=None)
    raw_material_medium_class: Mapped[str | None] = mapped_column(String(120), default=None)
    region_code: Mapped[str | None] = mapped_column(String(32), default=None)
    region_code_name: Mapped[str | None] = mapped_column(String(120), default=None)
    process_code: Mapped[str | None] = mapped_column(String(32), default=None)
    process_code_name: Mapped[str | None] = mapped_column(String(120), default=None)
    raw_material_status_code: Mapped[str | None] = mapped_column(String(32), default=None)
    raw_material_status_code_name: Mapped[str | None] = mapped_column(String(120), default=None)
    # The portal answers these as `YYYYMMDD` strings, and they are the material's
    # own validity, not a timestamp of ours: stored as sent, so a record that
    # carries a partial or malformed date still lands.
    valid_start_date: Mapped[str | None] = mapped_column(String(20), default=None)
    valid_end_date: Mapped[str | None] = mapped_column(String(20), default=None)
    use_yn: Mapped[str | None] = mapped_column(String(4), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
