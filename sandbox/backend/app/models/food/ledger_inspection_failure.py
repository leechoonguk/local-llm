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

# `3000222960` (10) for the serial, 품목제조보고번호 12-15, 인허가번호 11 -
# measured over the whole feed (572 rows, 2026-09-14).
CODE_LENGTH = 32

# 식품유형 12 자 at the widest. The three key texts are wider and are not
# vocabularies the portal closes - 부적합항목 28, 기준규격 44, 검사결과 43 - so
# they are `Text`, as is every free-text column beside them.
NAME_LENGTH = 120


# ============================================================
# Classes
# ============================================================


class FoodLedgerInspectionFailure(Base, AuditMixin):
    """검사부적합(국내) 원장 - our own copy of 식품안전나라 I2620.

    One row per failed test item: 572 rows over the whole feed (2026-09-14).
    The serial alone does not identify a row - 572 rows carry 479 distinct
    `disposal_seq`, because one disposal is several failed items (3000232082 is
    four 농약 on one 로즈마리) and one item can be judged against several
    standards (3000231595 살모넬라균, 내용물 1/6/13). The key is the triple
    (serial, 부적합항목, 기준규격), which is 570 of the 572; the two it collapses
    are rows the portal sends twice, identical in all eighteen columns.

    **The 품목제조보고번호 is on 84 of 572 rows (14.7 %).** Most inspections here
    are of 농·수·축산물, which have no 품목제조보고 at all - the ledger keeps them,
    and the derived event table decides what they can be joined to.
    """

    __tablename__ = "food_ledger_inspection_failure"
    __table_args__ = (
        UniqueConstraint(
            "disposal_seq",
            "test_item_name",
            "standard_text",
            name="uq_food_ledger_inspection_failure_natural_key",
        ),
        Index("ix_food_ledger_inspection_failure_item_report_no", "item_report_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    disposal_seq: Mapped[str] = mapped_column(String(CODE_LENGTH))
    test_item_name: Mapped[str] = mapped_column(Text)
    standard_text: Mapped[str] = mapped_column(Text)
    test_result_text: Mapped[str | None] = mapped_column(Text, default=None)
    institution_name: Mapped[str | None] = mapped_column(Text, default=None)
    item_report_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    license_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    address: Mapped[str | None] = mapped_column(Text, default=None)
    barcode_no: Mapped[str | None] = mapped_column(Text, default=None)
    packaging_unit: Mapped[str | None] = mapped_column(Text, default=None)
    manufactured_text: Mapped[str | None] = mapped_column(Text, default=None)
    shelf_life_text: Mapped[str | None] = mapped_column(Text, default=None)
    product_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    # 등록일, written with dots ("2026.03.11") where I0490 writes a timestamp -
    # the ledger keeps the publisher's string, and the derivation reads a date
    # out of it.
    registered_on: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
