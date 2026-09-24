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

# `3000234541` (10) for the serial, 품목제조보고번호 12-15, 인허가번호 11 -
# measured over the whole feed (376 rows, 2026-09-14), the same bound as every
# sibling ledger of this portal.
CODE_LENGTH = 32

# The closed vocabularies: 품목유형 42 자 at the widest, 식품분류 14, 회수등급 4.
# Free text - 제품명, 업소명, 회수사유, 회수방법, 유통기한, 포장단위, 제조일자
# and the image URL (542) - is `Text`, because none of those is a vocabulary the
# portal closes.
NAME_LENGTH = 120


# ============================================================
# Classes
# ============================================================


class FoodLedgerRecall(Base, AuditMixin):
    """회수·판매중지 원장 - our own copy of 식품안전나라 I0490.

    One row per 회수·판매중지 record: 376 rows over the whole feed (2026-09-14),
    one window of the RANGE walk. `recall_disuse_seq` is distinct on every one
    of them and never empty, so it alone is the natural key.

    **The 품목제조보고번호 is on half the feed.** 192 of 376 rows (51.1 %) carry
    one; the rest are 농·수산물 and imported goods with no 품목제조보고. The
    ledger keeps every row - what the portal published is what the ledger holds -
    and the derived event table decides what a row without a number can be
    joined to.
    """

    __tablename__ = "food_ledger_recall"
    __table_args__ = (
        UniqueConstraint("recall_disuse_seq", name="uq_food_ledger_recall_natural_key"),
        Index("ix_food_ledger_recall_item_report_no", "item_report_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    recall_disuse_seq: Mapped[str] = mapped_column(String(CODE_LENGTH))
    item_report_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    license_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    address: Mapped[str | None] = mapped_column(Text, default=None)
    # Empty on all 376 rows (2026-09-14); kept because the portal publishes the
    # column and a row that starts carrying one is not a contract change.
    telephone: Mapped[str | None] = mapped_column(Text, default=None)
    barcode_no: Mapped[str | None] = mapped_column(Text, default=None)
    packaging_unit: Mapped[str | None] = mapped_column(Text, default=None)
    # 제조일자 is free text here, not a date: "데이터없음", "(포장일자) 2026.4.2"
    # and "20260819" all appear on the same feed.
    manufactured_text: Mapped[str | None] = mapped_column(Text, default=None)
    recall_reason: Mapped[str | None] = mapped_column(Text, default=None)
    recall_method: Mapped[str | None] = mapped_column(Text, default=None)
    recall_grade: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    shelf_life_text: Mapped[str | None] = mapped_column(Text, default=None)
    product_type_group: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    product_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    product_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    image_url: Mapped[str | None] = mapped_column(Text, default=None)
    # 등록일, to the microsecond ("2026-09-14 17:19:13.501282") - the day this
    # event entered the registry, and what the derived table dates it by.
    registered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True
    )
