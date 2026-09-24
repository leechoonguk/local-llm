# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Constants
# ============================================================

# `202410221000001856` (18), 품목제조보고번호 19, 바코드 14 - the same bound as
# the sibling ledgers.
CODE_LENGTH = 32

# The label's closed vocabularies: 기준량 4 values, 영양성분구분 4, 서식 9,
# 성분단위 9 and 영양성분명 84, the widest of them 49 characters (whole feed,
# 2026-09-12). 제품명·업소명·비고 are free text and go to `Text`.
NAME_LENGTH = 120

# The panel's numbers arrive as the strings the publisher printed
# (`215.000`, `38.00`), 14 characters at the widest. They stay strings here:
# a ledger is the feed, and the reading into `Numeric` belongs to
# `food_label_nutrient`, which is where a number is claimed.
AMOUNT_LENGTH = 32

# `20241101`, `99991231`.
DATE_LENGTH = 20

# `Y`/`N`.
FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodLedgerQrNutrition(Base, AuditMixin):
    """푸드QR 영양표시정보 원장 - our own copy of `getFoodQrProdNsd02`.

    One row per printed panel entry: 25,663 records over 2,725 라벨 (whole feed,
    2026-09-12). The pair (`label_no`, `nutrition_detail_serial`) is the
    identity - 25,663 distinct, where the detail serial alone repeats (24,766).

    This is the feed that carries 품목보고번호 (`item_report_no`, filled on every
    record), so it is what joins the label axis to `food_item_report` once the
    derivation runs.
    """

    __tablename__ = "food_ledger_qr_nutrition"
    __table_args__ = (
        UniqueConstraint(
            "label_no", "nutrition_detail_serial", name="uq_food_ledger_qr_nutrition_natural_key"
        ),
        Index("ix_food_ledger_qr_nutrition_source_updated_at", "source_updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    label_no: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    item_report_serial: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    item_report_no: Mapped[str | None] = mapped_column(
        String(CODE_LENGTH), default=None, index=True
    )
    nutrition_label_serial: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    nutrition_detail_serial: Mapped[str] = mapped_column(String(CODE_LENGTH))
    barcode_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    version_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    valid_from: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    valid_to: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    basis_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    total_content_amount: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    total_content_unit: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    unit_content_amount: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    unit_content_unit: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    remark_text: Mapped[str | None] = mapped_column(Text, default=None)
    format_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    label_group_name: Mapped[str | None] = mapped_column(Text, default=None)
    unit_content_label_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    unit_content_label_amount_name: Mapped[str | None] = mapped_column(
        String(NAME_LENGTH), default=None
    )
    total_piece_label_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    nutrient_kind_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    nutrient_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    nutrient_sequence: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    amount: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    amount_unit: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    amount_unit_etc: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    daily_value_pct: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    additional_item_division_yn: Mapped[str | None] = mapped_column(
        String(FLAG_LENGTH), default=None
    )
    additional_item_division_name: Mapped[str | None] = mapped_column(
        String(NAME_LENGTH), default=None
    )
    additional_item_1_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    additional_item_2_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    additional_item_3_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    additional_item_4_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    additional_item_5_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    additional_item_1_amount: Mapped[str | None] = mapped_column(
        String(AMOUNT_LENGTH), default=None
    )
    additional_item_2_amount: Mapped[str | None] = mapped_column(
        String(AMOUNT_LENGTH), default=None
    )
    additional_item_3_amount: Mapped[str | None] = mapped_column(
        String(AMOUNT_LENGTH), default=None
    )
    additional_item_4_amount: Mapped[str | None] = mapped_column(
        String(AMOUNT_LENGTH), default=None
    )
    additional_item_5_amount: Mapped[str | None] = mapped_column(
        String(AMOUNT_LENGTH), default=None
    )
    additional_item_1_ratio: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    additional_item_2_ratio: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    additional_item_3_ratio: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    additional_item_4_ratio: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    additional_item_5_ratio: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    additional_item_1_unit_etc: Mapped[str | None] = mapped_column(
        String(AMOUNT_LENGTH), default=None
    )
    additional_item_2_unit_etc: Mapped[str | None] = mapped_column(
        String(AMOUNT_LENGTH), default=None
    )
    additional_item_3_unit_etc: Mapped[str | None] = mapped_column(
        String(AMOUNT_LENGTH), default=None
    )
    additional_item_4_unit_etc: Mapped[str | None] = mapped_column(
        String(AMOUNT_LENGTH), default=None
    )
    additional_item_5_unit_etc: Mapped[str | None] = mapped_column(
        String(AMOUNT_LENGTH), default=None
    )
    intake_basis_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    intake_amount: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    intake_amount_unit: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    intake_weight: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    intake_weight_unit: Mapped[str | None] = mapped_column(String(AMOUNT_LENGTH), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
