# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Index, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.food.item_report import FoodItemReport


# ============================================================
# Constants
# ============================================================

# A digest key (`I…`/`D…` plus 16 hex characters) and the closed vocabularies a
# declaration picks from; both fit well inside this.
CODE_LENGTH = 32

NAME_LENGTH = 120

# `20180810 ~ 20280809` (19 measured) and its two halves.
DATE_TEXT_LENGTH = 40

# Which registry the product belongs to - the same vocabulary
# `food_item_report` keys its rows by, declared here because a derivation reads
# its own model module and never another table's (rule://backend-ledger).
DOMESTIC_KIND = "domestic"
LIVESTOCK_KIND = "livestock"
IMPORT_KIND = "import"
HEALTH_FUNCTIONAL_KIND = "health_functional"

# 보고년도, four digits - the year a 생산실적 declaration is about.
YEAR_LENGTH = 8

# 생산량 and 연간생산능력 are published as digit strings in KG (옹기류 counts
# pieces) and become numbers here: 11 digits at the widest, three decimals on
# the 축산물 feed (`29.339`), so 18 and 3 hold every value measured 2026-09-15.
QUANTITY_PRECISION = 18

QUANTITY_SCALE = 3

# What a declaration is. 수입신고 writes the publisher's own 신고구분; the three
# 생산실적 feeds publish no such word, so the derivation writes this one - the
# kind is what tells the two apart in one table.
PRODUCTION_DECLARATION_KIND = "생산실적"

NATURAL_KEY = ("report_kind", "declaration_key")

SYNCED_COLUMNS = (
    "item_report_no",
    "declaration_kind",
    "export_country",
    "processed_date",
    "expiry_from",
    "expiry_to",
    "report_year",
    "production_qty_kg",
    "annual_capacity_kg",
)


# ============================================================
# Classes
# ============================================================


class FoodItemReportDeclaration(AuditMixin, Base):
    """One declaration of a reported product - the times it was declared, not the product.

    Derived off the 수입신고별 한글표시사항 ledger: 1,055,682 rows (2026-09-14),
    one per 수입신고, against the 292,867 products they declare. A product is
    what `food_item_report` holds; how often and under what dates it crossed a
    border is what this table holds, and the two would fight in one row - the
    same 제품 appears under 3.6 declarations on average and under 1,388 at the
    widest.

    The structure is general and two kinds fill it. `report_kind` is part of
    the key because a 식품 declares too: 생산실적 (I0300·I1420·I0310)
    is a declaration a product makes once a year, and it lands here rather than
    in a table of its own - the key was already (registry, declaration) and the
    only thing a second kind needed was its own columns.

    | kind | fills | leaves NULL |
    | --- | --- | --- |
    | 수입신고 | 수출국, 처리일자, 유통기한 | 보고년도, 생산량, 연간생산능력 |
    | 생산실적 | 보고년도, 생산량, 연간생산능력 | 수출국, 처리일자, 유통기한 |

    **Only what a declaration alone knows.** The product's own columns -
    수입업체, 제품명, 영문명, 해외제조업소, 제조국 - were written here until
    2026-09-14 and are gone: they are what `item_report_no` reaches, and a
    second copy is a second thing to keep true. `expiry_text` went with them,
    because `expiry_from`/`expiry_to` are that same text parsed and the ledger
    keeps the publisher's string as published.

    | column | verdict | why |
    | --- | --- | --- |
    | `report_kind`, `declaration_key` | keep | the key |
    | `item_report_no` | keep | the edge to the product |
    | `declaration_kind` | keep | 신고구분, a fact of this crossing |
    | `export_country` | keep | 수출국 varies between declarations of one product |
    | `processed_date` | keep | 처리일자 - what this table exists to date |
    | `expiry_from`, `expiry_to` | keep | the 유통기한 of this package |
    | 수입업체·제품명·영문명·해외제조업소·제조국 | dropped | the product row holds them |
    | `expiry_text` | dropped | the unparsed form of `expiry_from`/`expiry_to` |

    **The key is a digest, not a sequence.** The publisher states no key, so
    `declaration_key` is `D` plus the first 16 hex characters of the SHA-256 of
    the ledger's nine-column natural key, joined by U+001F - and
    `item_report_no` is `I` plus the same digest of the five columns that
    identify the product (see `services/food/item_report.py`). Both are
    deterministic: the derive job deletes and rewrites this table every night
    and a row keeps its number, which is what makes the number quotable.
    """

    __tablename__ = "food_item_report_declaration"
    __table_args__ = (
        UniqueConstraint(
            "report_kind", "declaration_key", name="uq_food_item_report_declaration_natural_key"
        ),
        Index(
            "ix_food_item_report_declaration_report",
            "report_kind",
            "item_report_no",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    report_kind: Mapped[str] = mapped_column(String(CODE_LENGTH))
    declaration_key: Mapped[str] = mapped_column(String(CODE_LENGTH))
    item_report_no: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    declaration_kind: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    # 수출국, which belongs to the crossing and not to the product: the same
    # product is declared out of more than one country (measured 2026-09-14).
    export_country: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    # Indexed because "what was declared that day" is the question a declaration
    # table answers that a product table cannot.
    processed_date: Mapped[str | None] = mapped_column(
        String(DATE_TEXT_LENGTH), default=None, index=True
    )
    expiry_from: Mapped[str | None] = mapped_column(String(DATE_TEXT_LENGTH), default=None)
    expiry_to: Mapped[str | None] = mapped_column(String(DATE_TEXT_LENGTH), default=None)
    # The three columns a 생산실적 declaration fills and an import declaration
    # leaves NULL, as an import declaration fills 수출국·처리일자·유통기한 and a
    # 생산실적 one leaves those NULL. One meaning per column: nothing here is
    # reused across kinds.
    report_year: Mapped[str | None] = mapped_column(String(YEAR_LENGTH), default=None, index=True)
    production_qty_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(QUANTITY_PRECISION, QUANTITY_SCALE), default=None
    )
    annual_capacity_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(QUANTITY_PRECISION, QUANTITY_SCALE), default=None
    )

    # Every declaration resolves to its product: the digest is computed from
    # columns this row carries, so the edge is total by construction -
    # 1,055,682 of 1,055,682 (2026-09-14). `viewonly`, because the derive job
    # writes both tables and a relationship that could write would be a second
    # writer (rule://backend-relations).
    item_report: Mapped[FoodItemReport] = relationship(
        primaryjoin=lambda: (
            (foreign(FoodItemReportDeclaration.report_kind) == FoodItemReport.report_kind)
            & (foreign(FoodItemReportDeclaration.item_report_no) == FoodItemReport.item_report_no)
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
