# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Constants
# ============================================================

# `8805522061018` - 27 characters at the widest over the whole feed (259,669
# records, 2026-09-12), and 품목보고번호 reaches 16. The same bound as the
# sibling ledgers' codes covers both.
CODE_LENGTH = 32

# 식품 유형 (55 characters at the widest), 업종 (12) and 주소 (15 - the feed
# carries 시도/시군구 only). The product and the maker are free text and go
# to `Text`, as does 소비기한, which is a sentence ("제조일로부터 12개월까지").
NAME_LENGTH = 120

# `20090724` - the portal's dates, and the undashed form is all it sends.
DATE_LENGTH = 20


# ============================================================
# Classes
# ============================================================


class FoodLedgerBarcode(Base, AuditMixin):
    """바코드연계제품정보 원장 - our own copy of the C005 records.

    One row per (유통바코드, 품목보고번호) pair, which is what the feed
    identifies a record by. Measured over the whole feed (259,669 records,
    2026-09-12): 229,040 distinct barcodes and 149,006 distinct 품목보고번호,
    so neither is unique on its own — a product registers several barcodes and
    a barcode is reused across registrations — while the pair is the record.
    13,474 records repeat a pair the feed already sent, and the stage folds
    each of those into one row.

    **This is not the ledger revisions 118-120 dropped.** That one was I2570
    (유통바코드), whose 53,242 rows all carried `LAST_UPDT_DTM` 2015-01-22 —
    a snapshot that could never refresh. C005 is live: the tail of this feed
    carries 보고일자 20260821 and the walk is 261 windows.

    There is no `source_updated_at`: the service publishes no row timestamp,
    only the 보고일 and 생산중단일 of the product, so a pass has nothing to
    compare readings by and the stage keeps the first of a repeated pair.
    """

    __tablename__ = "food_ledger_barcode"
    __table_args__ = (
        UniqueConstraint(
            "barcode_no",
            "item_report_no",
            name="uq_food_ledger_barcode_natural_key",
        ),
        Index("ix_food_ledger_barcode_item_report_no", "item_report_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    barcode_no: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    item_report_no: Mapped[str] = mapped_column(String(CODE_LENGTH))
    permit_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    production_end_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    shelf_life: Mapped[str | None] = mapped_column(Text, default=None)
    product_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    industry_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    site_address: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    closed_business_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
