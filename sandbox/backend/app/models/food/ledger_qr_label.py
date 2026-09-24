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

# `202410221000001856` - 18 characters on every one of the 2,278 records
# (whole feed, 2026-09-12), and the barcode is 14. The same bound as the
# sibling ledgers.
CODE_LENGTH = 32

# 식품구분 and 식품유형 are closed vocabularies the publisher picks from
# (`가공식품`, `즉석조리식품`); 54 characters at the widest. The label's own
# text - 내용량, 소비기한 문구, 섭취방법, 기능성정보 (863 characters) - is not,
# and goes to `Text`.
NAME_LENGTH = 120

# `20241101`, and `99991231` for a label with no end date.
DATE_LENGTH = 20

# `Y`/`N`.
FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodLedgerQrLabel(Base, AuditMixin):
    """푸드QR 식품표시정보 원장 - our own copy of `getFoodQrIndctInfo02`.

    One row per E라벨관리번호: the 표시사항 a package carries, as the publisher
    recorded it. 2,278 records over the whole feed (2026-09-12), every one with
    a distinct `label_no`, so the key is the number alone.

    The two sibling ledgers (`food_ledger_qr_nutrition`,
    `food_ledger_qr_allergy`) carry the same `label_no` and hold the panel and
    the allergens; none of the three is an edge's endpoint - the derived
    `food_label` family is (rule://backend-relations).

    `source_updated_at` is the publisher's `MDFCN_DT`, which this service
    answers as a date (`2026-07-30`) where its siblings answer a full stamp.
    """

    __tablename__ = "food_ledger_qr_label"
    __table_args__ = (Index("ix_food_ledger_qr_label_source_updated_at", "source_updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    label_no: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True)
    food_label_serial: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    barcode_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    version_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    valid_from: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    valid_to: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    food_division_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    food_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
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
    content_amount_text: Mapped[str | None] = mapped_column(Text, default=None)
    shelf_life_text: Mapped[str | None] = mapped_column(Text, default=None)
    intake_method_text: Mapped[str | None] = mapped_column(Text, default=None)
    functional_info_text: Mapped[str | None] = mapped_column(Text, default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
