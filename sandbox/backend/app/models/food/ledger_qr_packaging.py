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


class FoodLedgerQrPackaging(Base, AuditMixin):
    """푸드QR 용기·포장재질 원장 - our own copy of `getFoodQrIndctPackInfo02`.

    One row per packaging part: 6,914 rows over 3,809 라벨 (whole feed,
    2026-09-13) - the widest label set of the 푸드QR family.

    The key needs three parts: (라벨관리번호, 상세일련번호) collapses to 4,715
    because the same part is reported under two 품목제조보고 serials, so the
    serial completes it.
    """

    __tablename__ = "food_ledger_qr_packaging"
    __table_args__ = (
        UniqueConstraint(
            "label_no",
            "detail_serial",
            "item_report_serial",
            name="uq_food_ledger_qr_packaging_natural_key",
        ),
        Index("ix_food_ledger_qr_packaging_source_updated_at", "source_updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    label_no: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    detail_serial: Mapped[str] = mapped_column(String(CODE_LENGTH))
    item_report_serial: Mapped[str] = mapped_column(String(CODE_LENGTH))
    packaging_text: Mapped[str | None] = mapped_column(Text, default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    barcode_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    version_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    valid_from: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    valid_to: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
