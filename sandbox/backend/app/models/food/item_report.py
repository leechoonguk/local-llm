# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, String, Text, UniqueConstraint, Uuid, and_
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.food import ledger_health_functional_item_report as ledger_health_functional
from app.models.food import ledger_import_food_label, ledger_item_report
from app.models.food import ledger_livestock_item_report_raw_material as ledger_livestock
from app.models.food import product_classification as classification
from app.models.food.product_classification import FoodProductClassification


if TYPE_CHECKING:  # the child imports this module, so the parent names it by string
    from app.models.food.item_report_ingredient import FoodItemReportIngredient
    from app.models.food.label import FoodLabel
    from app.models.food.nutrition import FoodNutrition


# ============================================================
# Constants
# ============================================================

# `1955050900169` - 13 digits, 16 at the widest on either registry (I1250 and
# C006, whole feeds, 2026-09-08). `license_no` is 11 at the widest.
CODE_LENGTH = 32

# Which registry a report belongs to: `food` (I1250, 식품·첨가물) or `livestock`
# (C006, 축산물). The two number their reports in separate spaces - measured
# 2026-09-08, not one of C006's 567,910 품목제조번호 is in I1250 - so the kind is
# part of the key rather than a label beside it.
# `health_functional` is 17 characters, which is what the first rebuild of the
# fourth registry found against a 16-character column (2026-09-15).
KIND_LENGTH = 32
# Which registry reported a product, and the four are different publishers, not
# four spellings of one - each is the subject of its own law, which is the word
# the screen prints: I1250 is 식품 (식품위생법), C006 축산물 (축산물 위생관리법),
# I0030 건강기능식품 (건강기능식품법), and the 수입신고 feed is 수입식품
# (수입식품안전관리 특별법), whatever the product would be called at home.
# `domestic` was called `food` until the import registry arrived and "food"
# stopped telling a reader which of the two it meant.
DOMESTIC_KIND = ledger_item_report.REPORT_KIND
LIVESTOCK_KIND = ledger_livestock.REPORT_KIND
IMPORT_KIND = ledger_import_food_label.REPORT_KIND
# 건강기능식품 (I0030, 46,086 reports, 2026-09-15): a fourth registry with its own
# numbering space, its own 유형 vocabulary and four columns nothing else
# publishes (주된기능성, 섭취시주의사항, 보관방법, 기준규격).
HEALTH_FUNCTIONAL_KIND = ledger_health_functional.REPORT_KIND
KINDS = (DOMESTIC_KIND, LIVESTOCK_KIND, IMPORT_KIND, HEALTH_FUNCTIONAL_KIND)

# The portal's closed vocabularies (`혼합간장`, `포장육`, `식품제조가공업`): 27
# characters at the widest across both feeds. Free text is `Text`, below.
NAME_LENGTH = 120

# `20030825` - 8 characters on every measured record of either feed.
DATE_LENGTH = 20

FLAG_LENGTH = 4

# What identifies a report across passes, and the columns a pass fills beside
# it - I1250's nineteen. Listed here and not on a request schema because
# nothing but the derivation writes this table.
NATURAL_KEY = ("report_kind", "item_report_no")
SYNCED_COLUMNS = (
    "license_no",
    "business_name",
    "maker_name",
    "origin_country",
    "report_date",
    "product_name",
    "product_name_en",
    "primary_functionality",
    "intake_caution",
    "storage_method",
    "standard_spec",
    "functional_indicator",
    "product_type_name",
    "production_ended",
    "high_calorie_low_nutrition",
    "child_favorite_certified_yn",
    "shelf_life",
    "industry_name",
    "quality_maintenance_days",
    "usage_method",
    "purpose",
    "product_form",
    "packaging_material",
    "domestic_export_type",
    "source_updated_at",
)


# ============================================================
# Classes
# ============================================================


class FoodItemReport(Base, AuditMixin):
    """One reported product, whichever registry reported it - 품목제조보고, both kinds in one table.

    Derived, not fed: no portal operation answers this table. The I1250 pass
    writes the `food` slice and the C006 pass the `livestock` slice, each in the
    same transaction as its own ledger (`LedgerStage`, `within`), so a slice is
    exactly as old as the ledger it came from and a feed that failed leaves the
    other's rows alone. Measured 2026-09-08: 1,072,302 food rows + 567,910
    livestock rows = 1,640,212.

    **The livestock columns the feed does not carry are NULL, not invented.**
    C006 answers nine fields to I1250's nineteen: `license_no`, `business_name`,
    `report_date`, `product_name`, `product_type_name` and `source_updated_at`
    land here, and the eleven that describe how a product is made, kept and sold
    - `shelf_life`, `product_form`, `packaging_material`, `usage_method`,
    `purpose`, `industry_name`, `quality_maintenance_days`, `production_ended`,
    `high_calorie_low_nutrition`, `child_favorite_certified_yn`,
    `domestic_export_type` - are NULL on every livestock row (567,910 of
    1,640,212, 34.6 %). NULL here reads as "the registry does not publish it",
    which is what every nullable column in this tree already means.

    **One column, one meaning, all three kinds.** A column whose name said a
    domestic concept while holding a value all three registries answer was
    renamed; a column that is genuinely domestic keeps its name and is NULL on
    an import row. Decided 2026-09-14 over every column of this table:

    | column | verdict | why |
    | --- | --- | --- |
    | `report_kind`, `item_report_no` | keep | the key, and the join every child uses |
    | `business_name` | keep | 보고 업소 - 제조업소 domestically, 수입업체 on import |
    | `maker_name` | new | 제조업소 - equal to 보고 업소 domestically, 해외제조업소 on import |
    | `origin_country` | new | 제조국 - '대한민국' domestically, the declared country on import |
    | `product_name_en` | new | only I2790 publishes one |
    | `report_date` | renamed | 보고일자 on all three; nothing here is a permit |
    | `product_name`, `product_type_name` | keep | neutral; all three fill them |
    | `shelf_life` | keep, NULL on import | 소비기한 as a *period* - '제조일로부터 12개월'.
    The import registry answers a *range* ('20260807' ~ '20270806'), which is a
    different fact and lives where it was declared: `food_item_report_declaration`
    `expiry_from`/`expiry_to`, 679,275 rows of it (2026-09-15) |
    | the eleven domestic fields | keep, NULL on import | registry fields
    only I1250 publishes: `license_no`, `industry_name`,
    `domestic_export_type`, `production_ended`, `high_calorie_low_nutrition`,
    `child_favorite_certified_yn`, `quality_maintenance_days`, `usage_method`,
    `purpose`, `product_form`, `packaging_material` |

    No foreign key to either ledger: all three tables are deleted and refilled
    every night by their own passes, and a constraint between them would only
    dictate the order of two statements. The join back is
    `(report_kind, item_report_no)`, this table's own natural key.
    """

    __tablename__ = "food_item_report"
    __table_args__ = (
        UniqueConstraint("report_kind", "item_report_no", name="uq_food_item_report_natural_key"),
        CheckConstraint(
            "report_kind IN ('domestic', 'livestock', 'import', 'health_functional')",
            name="ck_food_item_report_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    report_kind: Mapped[str] = mapped_column(String(KIND_LENGTH))
    item_report_no: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    license_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    # 보고 업소: the business that reported the product to its registry - the
    # 제조업소 on I1250 and C006, the 수입업체 on I2790. One meaning, three feeds.
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    # 제조업소: who made it. Equal to `business_name` on a domestic report (the
    # registry names one business) and the 해외제조업소 on an import row, which is
    # the fact the two columns exist to keep apart.
    maker_name: Mapped[str | None] = mapped_column(Text, default=None)
    # 제조국. '대한민국' on both domestic registries - a fact of the registry, put
    # in the column rather than left for a reader to infer from `report_kind`.
    origin_country: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    # 보고일자: the 품목제조보고일 on a domestic report, the newest 수입신고 처리일자
    # on an import one. Renamed from `permit_date` on 2026-09-14: nothing here
    # is a permit, and the import rows made the domestic word wrong.
    report_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    # 영문 제품명. Only I2790 publishes one (149 characters at the widest,
    # measured 2026-09-14); NULL on the other two.
    product_name_en: Mapped[str | None] = mapped_column(Text, default=None)
    # What only 건강기능식품 reports carry, in neutral words: the function the
    # product claims, what to watch when taking it, how to keep it and the
    # standard it is judged against. NULL on the other three registries, which
    # publish none of them (measured 2026-09-15).
    primary_functionality: Mapped[str | None] = mapped_column(Text, default=None)
    intake_caution: Mapped[str | None] = mapped_column(Text, default=None)
    storage_method: Mapped[str | None] = mapped_column(Text, default=None)
    standard_spec: Mapped[str | None] = mapped_column(Text, default=None)
    # 기능지표성분 (`RAWMTRL_NM`): the 고시형 원료 the claim is indexed on, a
    # comma-joined list on 46,073 of 46,086 reports. A field, not ingredient
    # rows - the reason is measured in `services/food/item_report_ingredient`.
    functional_indicator: Mapped[str | None] = mapped_column(Text, default=None)
    # Indexed because "every report of this 식품유형" is why both kinds share a
    # table, and because it is the column a classification edge will join on.
    #
    # `Text`, not `String(NAME_LENGTH)`: the 수입신고 registry does not print a
    # closed vocabulary here. I1250 and C006 keep to 27 characters, but I2790's
    # `ITM_NM` runs to 221 (whole feed, 1,055,682 declarations, 2026-09-14 -
    # "과자(파이)…" with its parenthesised qualifiers), and a 120-character
    # column is what killed the first import rebuild.
    product_type_name: Mapped[str | None] = mapped_column(Text, default=None, index=True)
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
    # 식품유형명 to the 공전 type of that name, exactly: the portal writes the
    # name the same way on both (707 of 709 food names as written, 2026-09-08).
    # `food_product_classification` is the tree as it stands, so the one
    # condition left is the kind of node: a report names a type, and a tier of
    # the same name (카레(커리) L4 over 카레(커리) L5) is not it.
    #
    # Measured 2026-09-14 over the 313,505 rows of the import slice's own join:
    # 222,271 (70.9 %) name a type the 공전 lists, against 98.9 % domestic and
    # 99.9 % livestock. The gap is the registry, not the edge - I2790 prints
    # its own 식품유형 text ("과자(파이)…" out to 221 characters) where the two
    # 품목제조보고 registries pick from the 공전's own vocabulary - so an import
    # product's 기준규격 tab is empty about three times in ten.
    #
    # Measured 2026-09-08 over all 1,640,212 rows: 1,626,974 (99.2 %) resolve to
    # one type, 12,311 to none (조미김 6,801 - the type ended `20251231`, the
    # reports keep the name) and 927 to two or three - all 첨가물 the 공전 lists
    # under more than one 용도 (D08 일반식품첨가물 ↔ D09 가공보조제 / D10
    # 영양강화제), which no rule and no report column splits. Livestock resolves
    # better than food (567,510 of 567,910 to one): its 118 types are 포장육 and
    # its siblings, all current. Hence a list - one type for near enough all, and
    # the 927 told apart honestly rather than by "lowest code wins".
    product_classifications: Mapped[list[FoodProductClassification]] = relationship(
        primaryjoin=lambda: and_(
            foreign(FoodItemReport.product_type_name) == FoodProductClassification.korean_name,
            FoodProductClassification.product_yn == classification.IN_USE,
        ),
        uselist=True,
        viewonly=True,
        lazy="raise_on_sql",
    )
    # The 원재료 this product declares, in the order the label lists them.
    # Measured 2026-09-08: 1,072,171 of the 1,072,302 `food` reports carry a list
    # and 567,643 of 567,910 `livestock` ones do - a report with none is a
    # record the portal left the 원재료명 empty on, and it keeps an empty list
    # rather than disappearing. 10,135,735 rows in all, ~6 per report.
    #
    # Spelled as strings rather than lambdas, unlike every other edge here: the
    # child imports this module, so this side cannot name the class at runtime
    # and the registry resolves it instead (`TYPE_CHECKING` above is for the
    # annotation only).
    ingredients: Mapped[list[FoodItemReportIngredient]] = relationship(
        primaryjoin=(
            "and_("
            "FoodItemReport.report_kind == foreign(FoodItemReportIngredient.report_kind), "
            "FoodItemReport.item_report_no == foreign(FoodItemReportIngredient.item_report_no)"
            ")"
        ),
        order_by="FoodItemReportIngredient.position",
        uselist=True,
        viewonly=True,
        lazy="raise_on_sql",
    )
    # The 영양성분 records that name this report. Measured 2026-09-09: 149,639 of
    # 1,072,302 `food` reports (13.95 %) and 22,780 of 567,910 `livestock`
    # (4.01 %) have one - and 57 have two, the same food measured twice, so a
    # list. The rate is the nutrition database's reach: 4-7 % of reports
    # permitted before 2023, 32-34 % of 2024-2025.
    #
    # Strings for the same reason as `ingredients`: the child imports this module.
    nutritions: Mapped[list[FoodNutrition]] = relationship(
        primaryjoin=(
            "and_("
            "FoodItemReport.report_kind == foreign(FoodNutrition.report_kind), "
            "FoodItemReport.item_report_no == foreign(FoodNutrition.item_report_no)"
            ")"
        ),
        uselist=True,
        viewonly=True,
        lazy="raise_on_sql",
    )
    # The printed labels of this report - the 표시값 beside the 분석값
    # `nutritions` carries. A list, because a report is labelled more than once:
    # by two portals, and by several packages within one. Measured 2026-09-13
    # over both whole feeds: 푸드QR 4,765 labels and HACCP 14,664, sharing 56
    # 보고 numbers, together resolving to 9,750 rows here - against the
    # 1,640,212 this table holds.
    #
    # Strings for the same reason as `ingredients`: the child imports this
    # module.
    labels: Mapped[list[FoodLabel]] = relationship(
        primaryjoin=(
            "and_("
            "FoodItemReport.report_kind == foreign(FoodLabel.report_kind), "
            "FoodItemReport.item_report_no == foreign(FoodLabel.item_report_no)"
            ")"
        ),
        order_by="FoodLabel.source, FoodLabel.label_key",
        uselist=True,
        viewonly=True,
        lazy="raise_on_sql",
    )
