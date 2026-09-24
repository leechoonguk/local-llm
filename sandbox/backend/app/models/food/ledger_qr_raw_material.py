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

# `202410221000001856` (18), 품목보고번호 19, 바코드 14 - the same bound as the
# sibling ledgers.
CODE_LENGTH = 32

# The closed vocabularies a label picks from; free text - 제품명, 업소명, 표시
# 문구, 원재료 - is `Text` instead, and the reason is the width the feed
# measured (2026-09-13).
NAME_LENGTH = 120

# `20241101`, `99991231`.
DATE_LENGTH = 20


# ============================================================
# Classes
# ============================================================


class FoodLedgerQrRawMaterial(Base, AuditMixin):
    """푸드QR 원재료정보 원장 - our own copy of `getFoodQrProdRawmtrl02`.

    One row per 원재료표시 그룹: 2,301 rows over 2,156 라벨 (whole feed,
    2026-09-13). The text arrives as HTML on every row - each name wrapped in a
    네이버 사전 link, each origin in `<p class="bold">` - and is stored as sent,
    because a ledger is the feed. The derivation strips the tags.

    It is not a copy of `food_item_report_ingredient`: measured on the 2,012
    products both cover, this text carries a 함량 on 913 and an 원산지 on 1,594,
    where the registry split carries neither.
    """

    __tablename__ = "food_ledger_qr_raw_material"
    __table_args__ = (
        UniqueConstraint(
            "label_no", "raw_material_serial", name="uq_food_ledger_qr_raw_material_natural_key"
        ),
        Index("ix_food_ledger_qr_raw_material_source_updated_at", "source_updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    label_no: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    raw_material_serial: Mapped[str] = mapped_column(String(CODE_LENGTH))
    raw_material_group_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    raw_material_html: Mapped[str | None] = mapped_column(Text, default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    barcode_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    version_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    valid_from: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    valid_to: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
