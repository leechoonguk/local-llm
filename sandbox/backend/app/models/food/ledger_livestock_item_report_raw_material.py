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
# `food_item_report` and on every derived table that points at one (C006 축산물).
# Declared beside the feed rather than beside the product table, because the
# registry is what the feed *is* - a derivation may read it without reading
# another derived table (rule://backend-ledger).
REPORT_KIND = "livestock"

# The same registry numbering as the food ledgers: `item_report_no` is 12 to 15
# digits and `license_no` 11 (C006 sample, 2026-09-07, 4 windows / 3,988 rows).
CODE_LENGTH = 32

# Closed vocabulary (`포장육`, `소시지`, `양념육`): 27 distinct values, 8
# characters at the widest, in the same sample. Free text is `Text`, below.
NAME_LENGTH = 120

# `20040131` - 8 characters on every measured record.
DATE_LENGTH = 20


# ============================================================
# Classes
# ============================================================


class FoodLedgerLivestockItemReportRawMaterial(Base, AuditMixin):
    """축산물 품목제조보고(원재료) 원장 - our own copy of the C006 records.

    One row per reported livestock product (포장육, 양념육, 소시지, …), keyed
    by `item_report_no`. The number is issued by the same registry as the food
    ledgers' but the records live on a service of their own: C006 holds
    569,588 rows (2026-09-07) that I1250 and C002 do not - a 축산물가공품 the
    nutrition ledger names is found here and nowhere else in `food_*`. It is
    its own table for the reason C002 is: one operation, one pass, one
    quota, one ledger.

    **The ingredient list stays one string here**, as on
    `food_ledger_item_report_raw_material`: `raw_material_names` is the provider's
    comma-joined 원재료명 and `raw_material_ordinals` its 원재료표시순서, and
    the split into rows is `food_item_report_ingredient` (revision 135),
    which the same pass writes over, its `livestock` slice. This feed carries no
    내수/겸용 flag - the column set is C002's minus that one.

    `source_updated_at` is the provider's `CHNG_DT` (`20151102`), a reading of
    when the portal last touched the row; the pass walks the whole feed.
    """

    __tablename__ = "food_ledger_livestock_item_report_raw_material"
    # `item_report` is dropped from the index names, not from the table's: with it,
    # `ix_<table>_item_report_no` is 64 characters and `ix_<table>_source_updated_at`
    # 66, and PostgreSQL truncates an identifier at 63 silently - which is how two
    # indexes come to share a name. So this table names its indexes itself.
    __table_args__ = (
        Index(
            "ix_food_ledger_livestock_raw_material_item_report_no",
            "item_report_no",
            unique=True,
        ),
        Index("ix_food_ledger_livestock_raw_material_license_no", "license_no"),
        Index("ix_food_ledger_livestock_raw_material_source_updated_at", "source_updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    item_report_no: Mapped[str] = mapped_column(String(CODE_LENGTH))
    license_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    permit_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    product_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    raw_material_names: Mapped[str | None] = mapped_column(Text, default=None)
    raw_material_ordinals: Mapped[str | None] = mapped_column(Text, default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
