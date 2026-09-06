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

# `A10001` - 6 characters on every one of the 3,393 records (whole feed,
# 2026-09-06); the class codes are 1 and 2, the class sequences 10 digits.
# The same bound as the sibling ledgers.
CODE_LENGTH = 32

# The two class names are closed vocabularies (`일반성분 및 기능성분`, 15
# characters at the widest). The item's own names are not - `english_name`
# reaches 227 - and go to `Text`.
NAME_LENGTH = 120

# `Y`/`N`.
FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodTestItem(Base, AuditMixin):
    """시험항목 정보 원장 - our own copy of the I2530 records.

    One row per test item, keyed by `test_item_code`. The major and middle
    class of an item arrive as code, sequence and name on every record and
    are stored that way, on the row: the feed has no class operation to
    normalise them against, and a pass replaces the ledger as a set. A
    classification table is a derived one for the day a screen groups by it.

    The smallest feed of the portal (3,393 rows, four windows, ~1.5 s
    measured 2026-09-06), so the first the provider job walks.
    `source_updated_at` is the provider's `LAST_UPDT_DTM`
    (`2020-03-18 08:53:50.199009`), read as KST. `korean_name` is empty on
    132 records where `test_item_name` is not; both are kept as the wire
    sends them.
    """

    __tablename__ = "food_test_item"
    __table_args__ = (Index("ix_food_test_item_source_updated_at", "source_updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    test_item_code: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True)
    korean_name: Mapped[str | None] = mapped_column(Text, default=None)
    english_name: Mapped[str | None] = mapped_column(Text, default=None)
    abbreviation: Mapped[str | None] = mapped_column(Text, default=None)
    alias: Mapped[str | None] = mapped_column(Text, default=None)
    test_item_name: Mapped[str | None] = mapped_column(Text, default=None)
    major_class_sequence: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    major_class_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    major_class_korean_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    middle_class_sequence: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    middle_class_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    middle_class_korean_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    residue_definition: Mapped[str | None] = mapped_column(Text, default=None)
    in_use: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
