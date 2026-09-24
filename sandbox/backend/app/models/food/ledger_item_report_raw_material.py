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
# Constants
# ============================================================

# The same records as `food_ledger_item_report`, so the same bounds: `item_report_no`
# is 13 digits and 16 at the widest, `license_no` 11 (whole feed, 2026-09-06,
# 1,071,961 rows). Sample of C002 itself (2026-09-06, 3 windows): identical.
CODE_LENGTH = 32

# Closed vocabularies (`숙면`, `효소식품`): 23 characters at the widest on the
# sibling feed. Free text and the two comma-joined lists are `Text`, below.
NAME_LENGTH = 120

# `20020409` - 8 characters on every measured record.
DATE_LENGTH = 20

FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodLedgerItemReportRawMaterial(Base, AuditMixin):
    """식품(첨가물) 품목제조보고(원재료) 원장 - our own copy of the C002 records.

    One row per reported product, keyed by `item_report_no` - the same key and
    the same count as `food_ledger_item_report` (the provider's `total_count` is
    1,071,963 on both services, 2026-09-06): this feed is the *ingredients
    view* of that registry, not a child of it. It is its own table because
    it is its own operation with its own pass and quota - a sync that filled
    two feeds into one row would leave that row half-true whenever one of the
    two stopped on a refusal.

    **The ingredient list stays one string here.** `raw_material_names` is
    the provider's comma-joined 원재료명 (`밀가루, 정제수, 타피오카전분, …`)
    and `raw_material_ordinals` its 원재료표시순서 (`7,8,9,10,11,12`), stored
    as the portal joins them: the ledger keeps the wire's own shape. The
    split - one row per ingredient, ~10 per record, 8,723,725 rows measured
    2026-09-07 - is `food_item_report_ingredient` (revision 135), which the
    same pass writes over in the same transaction, its `food` slice.

    `source_updated_at` is the provider's `CHNG_DT` (`20230610`), a reading of
    when the portal last touched the row; the pass walks the whole feed.
    """

    __tablename__ = "food_ledger_item_report_raw_material"
    __table_args__ = (
        Index("ix_food_ledger_item_report_raw_material_source_updated_at", "source_updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    item_report_no: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True)
    license_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    permit_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    product_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    raw_material_names: Mapped[str | None] = mapped_column(Text, default=None)
    raw_material_ordinals: Mapped[str | None] = mapped_column(Text, default=None)
    domestic_export_type: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
