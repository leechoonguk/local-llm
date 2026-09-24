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

# Which registry this ledger is: the kind a report numbered here carries on
# `food_item_report` and on every derived table that points at one (I1250 식품).
# Declared beside the feed rather than beside the product table, because the
# registry is what the feed *is* - a derivation may read it without reading
# another derived table (rule://backend-ledger).
REPORT_KIND = "domestic"

# `1955050900169` - 13 digits, 16 at the widest over the first 194,000 records
# measured (2026-09-05). `license_no` is 11 at the widest.
CODE_LENGTH = 32

# Closed vocabularies the portal answers with (`혼합간장`, `식품제조가공업`,
# `해당없음`): 23 characters at the widest. Free text is `Text`, below.
NAME_LENGTH = 120

# `20030825` - 8 characters on every one of the 194,000 records measured.
DATE_LENGTH = 20

FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodLedgerItemReport(Base, AuditMixin):
    """식품(첨가물) 품목제조보고 원장 - our own copy of the I1250 records.

    The registry a product's 품목제조번호 points into: one row per
    reported product, keyed by `item_report_no` (품목제조보고번호), which is the
    report's own identity. The feed holds **1,071,979** records (the provider's
    own `total_count`, 2026-09-05); the width and key measurements below come
    from the first 194,000, which is where the hourly quota ended the measuring
    walk - a walk that ends on a refusal has not seen the end, and the first
    version of this docstring called 194,000 the whole feed. Within those,
    193,999 distinct numbers: the one collision (`1997040105594`) is two
    records with different content, which the upsert resolves to the later one
    (`version` 2 on that row after the first load).

    **Free text is `Text`.** `usage_method` reaches 1,376 characters in the
    measured sample,
    `packaging_material` 276, `shelf_life` 185, `product_form` 166 - these are
    sentences a manufacturer typed, and a bound on them was exceeded twice on
    the sibling ledger before it was dropped. Codes, dates and the portal's own
    closed vocabularies keep theirs: there a violation is a contract change.

    `source_updated_at` is the provider's `LAST_UPDT_DTM`, and on this feed it
    is real - `20260701` on a 2003 permit - where the barcode feed (I2570,
    retired at revision 119) stamped every row 2015. A reading of when the
    portal last touched the row; the pass walks the whole feed.
    """

    __tablename__ = "food_ledger_item_report"
    __table_args__ = (Index("ix_food_ledger_item_report_source_updated_at", "source_updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    item_report_no: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True)
    license_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    permit_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    product_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    production_ended: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    high_calorie_low_nutrition: Mapped[str | None] = mapped_column(
        String(NAME_LENGTH), default=None
    )
    child_favorite_certified_yn: Mapped[str | None] = mapped_column(
        String(FLAG_LENGTH), default=None
    )
    shelf_life: Mapped[str | None] = mapped_column(Text, default=None)
    industry_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    quality_maintenance_days: Mapped[str | None] = mapped_column(Text, default=None)
    usage_method: Mapped[str | None] = mapped_column(Text, default=None)
    purpose: Mapped[str | None] = mapped_column(Text, default=None)
    product_form: Mapped[str | None] = mapped_column(Text, default=None)
    packaging_material: Mapped[str | None] = mapped_column(Text, default=None)
    domestic_export_type: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
