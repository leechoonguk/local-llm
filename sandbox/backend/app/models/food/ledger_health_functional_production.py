# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Constants
# ============================================================

# 품목제조보고번호 (15 characters at the widest) and 인허가번호 (11) - the same
# numbers the report registries carry, in the same bound the siblings use.
CODE_LENGTH = 32

# 보고년도, four digits (`2016`-`2025` on this feed, 2026-09-15).
YEAR_LENGTH = 8

# 품목명 reaches 108 characters and 업소명 17; 품목유형 42. Free text is
# `Text`, the closed vocabularies are bounded here.
NAME_LENGTH = 200

# 생산량 and 연간생산능력 arrive as digit strings, 8 characters at the widest,
# some with a decimal point (`29.339`). They are kept **as sent**: the wire is
# text, and the number a screen reads is the derivation's (`food_item_report_production`).
QUANTITY_LENGTH = 32


# ============================================================
# Classes
# ============================================================


class FoodLedgerHealthFunctionalProduction(Base, AuditMixin):
    """건강기능식품 생산실적 원장 - our own copy of the I0310 records.

    One row per (품목제조보고번호, 보고년도, 품목명, 인허가번호): what a reported
    product produced in one year and what it could have produced. The key is
    four parts because the number alone repeats - 4,000 sampled rows of I0310
    held 3,985 distinct (번호, 년도) pairs and 4,000 distinct four-part keys
    (2026-09-15).

    316,747 rows over 2016-2025 (2026-09-15). The feed is walked one 보고년도
    at a time, because the years partition it exactly and the portal's latency
    grows with the offset inside whatever set is being walked.
    """

    __tablename__ = "food_ledger_health_functional_production"
    __table_args__ = (
        Index("ix_food_ledger_health_functional_production_item_report_no", "item_report_no"),
        Index("ix_food_ledger_health_functional_production_report_year", "report_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    item_report_no: Mapped[str] = mapped_column(String(CODE_LENGTH))
    report_year: Mapped[str] = mapped_column(String(YEAR_LENGTH))
    product_name: Mapped[str] = mapped_column(Text)
    license_no: Mapped[str] = mapped_column(String(CODE_LENGTH))
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    product_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    production_qty: Mapped[str | None] = mapped_column(String(QUANTITY_LENGTH), default=None)
    annual_capacity_qty: Mapped[str | None] = mapped_column(String(QUANTITY_LENGTH), default=None)
    # 품목구분 - 가공식품 / 건강기능식품 (6 characters at the widest).
    product_kind_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
