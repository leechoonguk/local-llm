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

# Every bound below is a whole-feed reading of I2610 (21 rows, measured
# 2026-09-07 after 19:00 KST - the service is closed 09:00-19:00, revision
# 122), taken as max(len) per column.

# `000008` (I2590 code, 6), `C0120010000000` (품목코드, 14 on every row of
# food_ledger_product_classification), `C20004` (시험항목코드, 6 on every row of
# food_ledger_test_item). The two names are 17 and 7 wide at most, kept `Text` as
# the portal's copies of another ledger's names.
CODE_LENGTH = 32


# ============================================================
# Classes
# ============================================================


class FoodLedgerCommonStandardExclusion(Base, AuditMixin):
    """공통기준제외 원장 - our own copy of the I2610 records.

    One row per (공통기준 group, 품목, 시험항목) a group rule of
    `food_ledger_common_standard` (I2600) does not apply to. The record carries no
    serial of its own, so the ledger's identity is the triple itself - three
    NOT NULL columns under one unique constraint - and a record missing any
    of the three is skipped at staging.

    Measured 2026-09-07 over the whole feed (21 rows): the triple is unique
    and no part of it is ever empty, so the key stands as documented.

    Joins, by value and without foreign keys (the ledgers are replaced
    independently every night): `common_standard_type_code` ↔
    `food_ledger_common_standard_type`, `product_code` ↔
    `food_ledger_product_classification.product_code`, `test_item_code` ↔
    `food_ledger_test_item.test_item_code`. The two names are the portal's copies,
    kept so a row reads on its own.

    `source_updated_at` is the provider's `LAST_UPDT_DTM` (KST), a reading of
    when the portal last touched the row; the pass walks the whole feed.
    """

    __tablename__ = "food_ledger_common_standard_exclusion"
    __table_args__ = (
        UniqueConstraint(
            "common_standard_type_code",
            "product_code",
            "test_item_code",
            name="uq_food_ledger_common_standard_exclusion_key",
        ),
        Index("ix_food_ledger_common_standard_exclusion_source_updated_at", "source_updated_at"),
        # `common_standard_` said once: the derived name repeats it and reaches 65
        # characters, and PostgreSQL truncates an identifier at 63 silently.
        Index("ix_food_ledger_common_standard_exclusion_type_code", "common_standard_type_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    common_standard_type_code: Mapped[str] = mapped_column(String(CODE_LENGTH))
    product_code: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    test_item_code: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    standard_name: Mapped[str | None] = mapped_column(Text, default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
