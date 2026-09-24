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
# `food_item_report` and on every derived table that points at one (I0490 수입신고).
# Declared beside the feed rather than beside the product table, because the
# registry is what the feed *is* - a derivation may read it without reading
# another derived table (rule://backend-ledger).
REPORT_KIND = "import"

# Which 제품구분 a row of this feed is a *product* under. The feed is every
# 수입신고 and states one of seven kinds; three of them are what `food_item_report`
# holds and the other four are not. Measured 2026-09-21 over the whole ledger,
# by whether the row's 품목유형 is a word the 품목제조보고 registries use:
#
#     가공식품      473,886 rows   95.3 % share the 식품공전 vocabulary
#     식품첨가물     67,532         81.5 %
#     건강기능식품   28,574         48.4 %
#     축산물        155,929         19.2 %  - 검역 분류 (돼지고기(냉동,정육…))
#     농.임산물      80,398          0.001 % - HS 품목명 (브로콜리(신선))
#     수산물         71,028          0 %
#     기구또는용기.포장 177,302       2.4 %  - not food at all
#
# So a derivation reads the first three: a product is what the registries
# number, and a 브로콜리(신선) or a 냉동 정육 is a crossing of a commodity, not
# a product under a 식품유형 this table's readers can compare. The other four
# stay in the ledger - the ledger is the feed whole (rule://backend-ledger) -
# and reach no derived table.
PRODUCT_DECLARATION_KINDS = ("가공식품", "식품첨가물", "건강기능식품")

# The closed vocabularies the feed picks from - 제품구분 (7 values) and the two
# country names. Measured over the whole feed (1,087,781 records, 2026-09-13).
NAME_LENGTH = 120

# `20180810 ~ 20280809` (19 at the widest, measured), and its two halves.
DATE_TEXT_LENGTH = 40


# ============================================================
# Classes
# ============================================================


class FoodLedgerImportFoodLabel(Base, AuditMixin):
    """수입신고별 한글표시사항 원장 - our own copy of the feed the screen publishes.

    One row per 수입신고: 1,087,781 records over the whole feed (2026-09-13),
    처리일자 1998-01-30 onward. It is the 수입식품조회 screen's population - the
    year histograms match the screen ledger of the night before to the digit
    (2022 4,704 · 2023 12,187 · 2024 80,914 · 2025 406,201) - so this feed
    replaced a paging crawl of that screen.

    `label_text` is why it is worth having: the printed 한글표시사항 in full,
    1,075,586 rows (98.9%) and up to 8,602 characters, carrying 원재료명 및 함량,
    영양정보, 내용량, 포장재질, 보관방법 and the allergen sentence as the label
    prints them. `Text`, because a published paragraph has no editorial width.
    The feed's own `IRDNT_NM` column is kept beside it but is nearly empty
    (7,743 rows, 0.7%), which is the measurement that says the ingredient list
    a reader wants is inside `label_text` - splitting it is a derived table's
    question (rule://backend-ledger).

    **The publisher states no key.** 수입업체 + 제품명 + 처리일자 + 유통기한 alone
    leave 1,017,499 distinct of 1,087,781 (93.5%), so the natural key below is
    every column the feed answers except the two texts, and the first live pass
    measures what that leaves.
    """

    __tablename__ = "food_ledger_import_food_label"
    __table_args__ = (
        UniqueConstraint(
            "importer_name",
            "product_name",
            "product_name_en",
            "product_type_name",
            "overseas_maker_name",
            "origin_country",
            "export_country",
            "processed_date",
            "expiry_text",
            name="uq_food_ledger_import_food_label_natural_key",
        ),
        Index("ix_food_ledger_import_food_label_processed_date", "processed_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    # Free text of the publisher's own width: 업체명 55, 제품명 119/149, 품목 221,
    # 해외업소 307 measured over the whole feed - all of them a name someone types,
    # so the bound would be an editorial guess (rule://backend-ledger).
    importer_name: Mapped[str] = mapped_column(Text)
    product_name: Mapped[str] = mapped_column(Text)
    product_name_en: Mapped[str] = mapped_column(Text)
    product_type_name: Mapped[str] = mapped_column(Text)
    overseas_maker_name: Mapped[str] = mapped_column(Text)
    origin_country: Mapped[str] = mapped_column(String(NAME_LENGTH))
    export_country: Mapped[str] = mapped_column(String(NAME_LENGTH))
    processed_date: Mapped[str] = mapped_column(String(DATE_TEXT_LENGTH))
    expiry_text: Mapped[str] = mapped_column(String(DATE_TEXT_LENGTH))
    declaration_kind: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    expiry_from: Mapped[str | None] = mapped_column(String(DATE_TEXT_LENGTH), default=None)
    expiry_to: Mapped[str | None] = mapped_column(String(DATE_TEXT_LENGTH), default=None)
    label_text: Mapped[str | None] = mapped_column(Text, default=None)
    raw_material_names: Mapped[str | None] = mapped_column(Text, default=None)
