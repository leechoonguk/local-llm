# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, Uuid
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

# What identifies a row across passes, and the columns the derivation fills
# beside it - the ledger's own, one for one. Listed on the model because nothing
# but the derive job writes this table.
NATURAL_KEY = ("test_item_code",)


# ============================================================
# Classes
# ============================================================


class FoodTestItem(Base, AuditMixin):
    """One 시험항목 - what a clause of either standard measures.

    Derived, not fed: no portal operation answers this table. The derive job
    rebuilds it off the I2570 ledger whole. Measured 2026-09-08: 3,393 items,
    and every `test_item_code` a standard names is here - 1,034 of 1,034 on the
    개별 side, 830 of 830 on the 공통 side.
    """

    __tablename__ = "food_test_item"

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
