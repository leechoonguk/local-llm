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

# Which registry this ledger is: the kind a report numbered here carries on
# `food_item_report` and on every derived table that points at one (I0030 건강기능식품).
# Declared beside the feed rather than beside the product table, because the
# registry is what the feed *is* - a derivation may read it without reading
# another derived table (rule://backend-ledger).
REPORT_KIND = "health_functional"

# `20140017002183` - 15 characters at the widest over the whole feed (46,086
# rows, 2026-09-15). 인허가번호 is 11.
CODE_LENGTH = 32

# The closed vocabularies this registry picks from: 유형 107 자 at the widest,
# 업종 11, 제품형태코드명 9, 고열량저영양 4, 생산종료 3. Everything a publisher
# writes as prose - 주된기능성 (1,494), 기준규격 (3,062), 섭취시주의사항 (1,242),
# the three 원재료 lists (1,742 / 1,313 / 296) - is `Text`, because a bound on
# free text buys nothing but an outage.
NAME_LENGTH = 120

# `20201027` - 8 characters on every record of the feed.
DATE_LENGTH = 20


# ============================================================
# Classes
# ============================================================


class FoodLedgerHealthFunctionalItemReport(Base, AuditMixin):
    """건강기능식품 품목제조신고 원장 - our own copy of 식품안전나라 I0030.

    One row per reported 건강기능식품: 46,086 rows over the whole feed
    (2026-09-15), 47 windows of the RANGE walk. `item_report_no` is filled on
    every one of them and is the natural key.

    **A fourth numbering space.** 식품 (I1250), 축산물 (C006) and this
    registry number their reports separately, so a number alone does not say
    which registry reported it - which is why the derived table keys on
    `(report_kind, item_report_no)` and this ledger is read under
    `health_functional`.

    What only this registry publishes: 주된기능성 (45,986 of 46,086),
    섭취시주의사항 (44,405), 보관방법 (3,248 - the one sparse column) and
    기준규격 (46,082), plus three separate 원재료 lists where the other
    registries send one.
    """

    __tablename__ = "food_ledger_health_functional_item_report"
    __table_args__ = (
        UniqueConstraint(
            "item_report_no", name="uq_food_ledger_health_functional_item_report_natural_key"
        ),
        Index("ix_food_ledger_health_functional_item_report_license_no", "license_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    item_report_no: Mapped[str] = mapped_column(String(CODE_LENGTH))
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    license_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    permit_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    product_type_name: Mapped[str | None] = mapped_column(Text, default=None)
    product_shape: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    product_form: Mapped[str | None] = mapped_column(Text, default=None)
    intake_method: Mapped[str | None] = mapped_column(Text, default=None)
    primary_functionality: Mapped[str | None] = mapped_column(Text, default=None)
    intake_caution: Mapped[str | None] = mapped_column(Text, default=None)
    storage_method: Mapped[str | None] = mapped_column(Text, default=None)
    standard_spec: Mapped[str | None] = mapped_column(Text, default=None)
    shelf_life: Mapped[str | None] = mapped_column(Text, default=None)
    packaging_material: Mapped[str | None] = mapped_column(Text, default=None)
    packaging_method: Mapped[str | None] = mapped_column(Text, default=None)
    functional_indicator: Mapped[str | None] = mapped_column(Text, default=None)
    # Three lists where the other registries send one: 기능성 원재료, 기타
    # 원재료 and 캡슐 원재료. Each stays the publisher's comma-joined string
    # here; the split into rows is the derivation's (rule://backend-ledger).
    functional_raw_material_names: Mapped[str | None] = mapped_column(Text, default=None)
    other_raw_material_names: Mapped[str | None] = mapped_column(Text, default=None)
    capsule_raw_material_names: Mapped[str | None] = mapped_column(Text, default=None)
    high_calorie_low_nutrition: Mapped[str | None] = mapped_column(
        String(NAME_LENGTH), default=None
    )
    production_ended: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    # Empty on all 46,086 rows (2026-09-15); kept because the portal publishes
    # the column and a row that starts carrying one is not a contract change.
    child_favorite_certified_yn: Mapped[str | None] = mapped_column(
        String(NAME_LENGTH), default=None
    )
    industry_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    source_updated_at: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
