# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.food.item_report import FoodItemReport


# ============================================================
# Constants
# ============================================================

CODE_LENGTH = 32

NAME_LENGTH = 120

DATE_LENGTH = 20

# `health_functional` (17) is the widest kind `food_item_report` keys by.
KIND_LENGTH = 32

# What identifies a row across passes, and what the derivation fills beside it -
# the ledger's own columns, one for one. Listed on the model because nothing but
# the derive job writes this table.
NATURAL_KEY = ("barcode_no", "item_report_no")


# ============================================================
# Classes
# ============================================================


class FoodBarcode(Base, AuditMixin):
    """One 유통바코드 under the 품목보고번호 it is sold as.

    Derived, not fed: the derive job rebuilds it off the C005 ledger whole, so
    that the edge below can live here rather than on the ledger
    (rule://backend-relations).

    Measured on the feed (2026-09-12, 259,669 records): 246,195 distinct pairs,
    229,040 barcodes and 149,006 품목보고번호 - a product registers several
    barcodes and a barcode is re-registered, so the pair is the row.

    **The columns beside the barcode are C005's statement about the product,
    not the product row's.** 제품명, 소비기한, 업소명 and the rest are what the
    barcode registry published, and they may disagree with `food_item_report`:
    measured 2026-09-15 over the 119,638 rows that resolve, 99.6 % carry the
    same 제품명 as the report they point at. The disagreement is the registry's
    and is kept, not overwritten.

    `report_kind` is not published by C005 at all - it is resolved at derive
    time by asking which of the three numbered registries carries the number,
    because the edge to a product is (report_kind, item_report_no) and nothing
    else (rule://backend-relations).

    The HACCP label feed carries a `barcode` column too and it is **not** read
    here: measured over its whole feed, 8,615 of 14,378 filled values are the
    literal `알수없음`, four are Excel's `9.99999E+99`, and the 5,692 numeric
    ones resolve to 5,283 distinct codes - a tenth of what C005 answers, in a
    column that would need a parser to tell a barcode from a sentence.
    """

    __tablename__ = "food_barcode"
    __table_args__ = (
        UniqueConstraint("barcode_no", "item_report_no", name="uq_food_barcode_natural_key"),
        Index("ix_food_barcode_item_report_no", "item_report_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    barcode_no: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    item_report_no: Mapped[str] = mapped_column(String(CODE_LENGTH))
    # Which registry the number belongs to, resolved at derive time against the
    # three numbered report ledgers - NULL when no registry carries it. C005
    # publishes the number alone, and the number alone is not the edge:
    # `food_item_report` is keyed by (report_kind, item_report_no).
    report_kind: Mapped[str | None] = mapped_column(String(KIND_LENGTH), default=None, index=True)
    report_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    production_end_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    shelf_life: Mapped[str | None] = mapped_column(Text, default=None)
    product_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    industry_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    site_address: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    closed_business_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)

    # The report the barcode is sold under - a logical join, never a foreign
    # key: both sides are rebuilt whole by the derive job, and a constraint
    # would make the order of two independent rebuilds a correctness question.
    # Both columns of the key, because `food_item_report` is keyed by both: a
    # number alone belongs to whichever registry numbered it, and three
    # registries number in separate spaces (rule://backend-relations).
    # Measured 2026-09-15 on the live tables: 119,638 of 246,195 rows resolve
    # (48.6 % - domestic 97,686, livestock 13,511, health_functional 8,441).
    # The rest name 품목보고번호 no registry carries any more - C005 keeps a
    # barcode after its product's report is withdrawn.
    item_report: Mapped[FoodItemReport | None] = relationship(
        primaryjoin=lambda: (
            (foreign(FoodBarcode.report_kind) == FoodItemReport.report_kind)
            & (foreign(FoodBarcode.item_report_no) == FoodItemReport.item_report_no)
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
