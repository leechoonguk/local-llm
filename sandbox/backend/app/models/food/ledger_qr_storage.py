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


class FoodLedgerQrStorage(Base, AuditMixin):
    """푸드QR 보관·취급방법 원장 - our own copy of `getFoodQrSfkpTrmtInfo02`.

    One row per printed 보관방법 문구: 2,868 rows over 2,155 라벨 (whole feed,
    2026-09-13). `실온보관`, `냉장보관(0~10℃)`, `냉동보관(-18℃ 이하)` - a storage
    band, which is not `food_item_report.shelf_life` (the 소비기한) and has no
    column anywhere else in this database.
    """

    __tablename__ = "food_ledger_qr_storage"
    __table_args__ = (
        UniqueConstraint("label_no", "detail_serial", name="uq_food_ledger_qr_storage_natural_key"),
        Index("ix_food_ledger_qr_storage_source_updated_at", "source_updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    label_no: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    detail_serial: Mapped[str] = mapped_column(String(CODE_LENGTH))
    storage_text: Mapped[str | None] = mapped_column(Text, default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    barcode_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    version_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    valid_from: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    valid_to: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
