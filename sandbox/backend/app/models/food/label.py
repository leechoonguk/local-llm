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

CODE_LENGTH = 32

NAME_LENGTH = 120

# `health_functional` (17) is the widest kind `food_item_report` keys by.
KIND_LENGTH = 32

DATE_LENGTH = 20

FLAG_LENGTH = 4

# Which portal printed this label. A label is never merged across the two: a
# 품목보고번호 covers several packages and the two portals hold different ones -
# measured 2026-09-13 on the 56 보고 both carry, 제품명 agrees on 34, 식품유형 on
# 37 and 내용량 on 11 (밀키스 `250mL` here against `250ml*6` there).
FOOD_QR_SOURCE = "food-qr"
HACCP_SOURCE = "haccp"
# The printed label of a 수입신고, parsed out of the paragraph the import feed
# publishes: 1,044,332 of 1,055,682 declarations carry one (98.9%, 2026-09-14).
# It is a third publisher and never merged with the other two - it describes the
# package that crossed the border, under that declaration's own key.
IMPORT_SOURCE = "import"
SOURCES = (FOOD_QR_SOURCE, HACCP_SOURCE, IMPORT_SOURCE)

# What a label says about allergens, which is three states and not two. Measured
# 2026-09-13 over both feeds: 7,815 labels declare at least one substance, 41
# say 없음 in so many words, and 9,084 say nothing a reader may act on - 8,479
# HACCP rows read 알수없음 and 576 푸드QR labels have no row in the 알레르기 feed
# at all.
#
# Collapsing the last two onto "no allergen" is the one mistake this column
# exists to prevent: 새우탕큰사발면 declares twelve substances on its 푸드QR label
# and 알수없음 on its HACCP one, and a screen that renders both as "none" tells a
# reader the second package is safe.
ALLERGEN_DECLARED = "declared"
ALLERGEN_NONE = "none"
ALLERGEN_UNKNOWN = "unknown"
ALLERGEN_DECLARATIONS = (ALLERGEN_DECLARED, ALLERGEN_NONE, ALLERGEN_UNKNOWN)

# What identifies a row across rebuilds, and what the derivation fills beside
# it. Listed on the model because nothing but the derive job writes this table.
NATURAL_KEY = ("source", "label_key")

SYNCED_COLUMNS = (
    "report_kind",
    "item_report_no",
    "allergen_declaration",
    "product_name",
    "barcode_no",
    "food_division_name",
    "food_type_name",
    "product_type_state",
    "content_amount_text",
    "shelf_life_text",
    "storage_text",
    "raw_material_text",
    "intake_method_text",
    "functional_info_text",
    "business_name",
    "maker_name",
    "seller_name",
    "representative_name",
    "site_address",
    "version_no",
    "valid_from",
    "valid_to",
    "history_tracked_yn",
    "irradiated_yn",
    "gmo_yn",
    "infant_sale_marked_yn",
    "high_calorie_low_nutrition_yn",
    "pasteurized_yn",
    "sterilized_yn",
    "refrigerated_yn",
)


# ============================================================
# Classes
# ============================================================


class FoodLabel(Base, AuditMixin):
    """One printed label of a product, from either portal that publishes them.

    Derived, not fed: the derive job rebuilds it off six ledgers - the 푸드QR
    표시사항 / 보관방법 / 원재료 / 품목제조정보 / 영양표시 family and the HACCP
    표기정보 feed - so the report's edge to it (`FoodItemReport.labels`) points
    at a derived table and not at a ledger (rule://backend-relations).

    Measured whole feeds (2026-09-13): 푸드QR knows 4,765 라벨 and HACCP 14,664
    품목보고번호, sharing 56 보고 numbers. Together they reach 9,750 rows of
    `food_item_report`, against the 1,911 the 표시사항 feed alone reached.

    `source` is half the key for the reason stated above the constant: the two
    portals hold different packages of one report, so a row here is one label,
    never a merge of two.

    **The columns here are what the label printed, not what the report says.**
    제품명, 소비기한, 업소명 and the rest are the label registry's statement about
    the package, and a product's own row may disagree - a label is printed once
    and a report is amended. The disagreement is kept.

    The printed 영양표시 is not a column and not a table: the 푸드QR panel was
    dropped from this axis on 2026-09-13, and the HACCP one never parsed
    (revision 170).
    """

    __tablename__ = "food_label"
    __table_args__ = (
        UniqueConstraint("source", "label_key", name="uq_food_label_natural_key"),
        Index("ix_food_label_item_report_no", "item_report_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(NAME_LENGTH), index=True)
    label_key: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    # Which registry the number belongs to. Known by construction on an import
    # label (this repository numbered it) and resolved against the three
    # numbered registries otherwise - NULL when none carries the number. The
    # edge to a product is (report_kind, item_report_no), never the number
    # alone (rule://backend-relations).
    report_kind: Mapped[str | None] = mapped_column(String(KIND_LENGTH), default=None, index=True)
    item_report_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    allergen_declaration: Mapped[str] = mapped_column(String(NAME_LENGTH), default=ALLERGEN_UNKNOWN)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    barcode_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    food_division_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    # `Text`: the 수입신고 registry prints its own 식품유형 here, and I2790's
    # `ITM_NM` runs to 221 characters (whole feed, 1,055,682 declarations,
    # 2026-09-14) where 푸드QR and HACCP keep to a closed vocabulary.
    food_type_name: Mapped[str | None] = mapped_column(Text, default=None)
    product_type_state: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    content_amount_text: Mapped[str | None] = mapped_column(Text, default=None)
    shelf_life_text: Mapped[str | None] = mapped_column(Text, default=None)
    storage_text: Mapped[str | None] = mapped_column(Text, default=None)
    raw_material_text: Mapped[str | None] = mapped_column(Text, default=None)
    intake_method_text: Mapped[str | None] = mapped_column(Text, default=None)
    functional_info_text: Mapped[str | None] = mapped_column(Text, default=None)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    maker_name: Mapped[str | None] = mapped_column(Text, default=None)
    seller_name: Mapped[str | None] = mapped_column(Text, default=None)
    representative_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    site_address: Mapped[str | None] = mapped_column(Text, default=None)
    version_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    valid_from: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    valid_to: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    history_tracked_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    irradiated_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    gmo_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    infant_sale_marked_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    high_calorie_low_nutrition_yn: Mapped[str | None] = mapped_column(
        String(FLAG_LENGTH), default=None
    )
    pasteurized_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    sterilized_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    refrigerated_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
