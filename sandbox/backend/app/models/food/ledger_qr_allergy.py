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

# `202410221000001856` (18), 일련번호 13, 바코드 14 - the same bound as the
# sibling ledgers.
CODE_LENGTH = 32

# The declared allergen as the publisher typed it: 22 characters at the widest
# (`조개류(굴,홍합,꼬막 포함)`) over the whole feed (2026-09-12). 제품명 and
# 표시그룹명 reach 40 and stay under the same bound.
NAME_LENGTH = 120

# `20241101`, `99991231`.
DATE_LENGTH = 20


# ============================================================
# Classes
# ============================================================


class FoodLedgerQrAllergy(Base, AuditMixin):
    """푸드QR 알레르기정보 원장 - our own copy of `getFoodQrAllrgyInfo02`.

    One row per declared allergen: 8,580 records over 1,746 라벨 (whole feed,
    2026-09-12), so a label that declares none simply has no row here - where
    the retired HACCP feed answered `알수없음` on 30.0 % of its split values
    (revision 171).

    `allergen_serial` is distinct on all 8,580 records on its own; it is keyed
    with its label so the pair reads as one identity, the way the 영양표시
    sibling's does.

    The names are the publisher's own text (`조개류(굴, 가리비)`, `조개류()`),
    kept as sent: normalising is the derived table's business.
    """

    __tablename__ = "food_ledger_qr_allergy"
    __table_args__ = (
        UniqueConstraint(
            "label_no", "allergen_serial", name="uq_food_ledger_qr_allergy_natural_key"
        ),
        Index("ix_food_ledger_qr_allergy_source_updated_at", "source_updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    label_no: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    allergen_serial: Mapped[str] = mapped_column(String(CODE_LENGTH))
    allergen_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None, index=True)
    item_report_serial: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    barcode_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    label_group_name: Mapped[str | None] = mapped_column(Text, default=None)
    version_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    valid_from: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    valid_to: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
