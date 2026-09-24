# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import String, Text, Uuid
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


class FoodLedgerHaccpLabel(Base, AuditMixin):
    """HACCP 표기정보 원장 - our own copy of `B553748/CertImgListServiceV3`.

    One row per 품목보고번호: 14,664 records, all distinct (whole feed,
    2026-09-13). This is the label axis's width - the 푸드QR family knows 4,765
    labels and this one 14,664 products, sharing only 56 보고 numbers.

    The printed 영양표시, the two image URLs and the barcode are **not** columns
    here: the seed leaves them on the wire (revision 198), because the panel
    needs a parser no one can write honestly (revision 170), the photographs
    have no reader, and C005 answers barcodes properly.

    `allergy_names` is stored as sent - 8,484 of its 14,664 values read
    `알수없음` - and the derivation is where those stop becoming rows.
    """

    __tablename__ = "food_ledger_haccp_label"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    item_report_no: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True)
    product_kind_division: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    raw_material_names: Mapped[str | None] = mapped_column(Text, default=None)
    allergy_names: Mapped[str | None] = mapped_column(Text, default=None)
    product_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    product_type_state: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    maker_name: Mapped[str | None] = mapped_column(Text, default=None)
    seller_name: Mapped[str | None] = mapped_column(Text, default=None)
    capacity_text: Mapped[str | None] = mapped_column(Text, default=None)
