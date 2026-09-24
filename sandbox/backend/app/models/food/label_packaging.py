# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.food.label import FoodLabel


# ============================================================
# Constants
# ============================================================

CODE_LENGTH = 32

NAME_LENGTH = 120

# Which portal printed the label this row belongs to - the same vocabulary
# `food_label` keys its rows by, declared here because a derivation reads its
# own model module and never another table's (rule://backend-ledger).
FOOD_QR_SOURCE = "food-qr"
HACCP_SOURCE = "haccp"
IMPORT_SOURCE = "import"

NATURAL_KEY = ("source", "label_key", "position")

SYNCED_COLUMNS = ("packaging_text",)


# ============================================================
# Classes
# ============================================================


class FoodLabelPackaging(Base, AuditMixin):
    """One packaging part of a label and what it is made of.

    Derived off the 푸드QR 용기·포장재질 ledger: 6,914 rows over 3,809 라벨
    (2026-09-13), the widest label set of that family.

    `food_item_report.packaging_material` states the same fact for 1,004,958
    reports as one string (`면-폴리프로필렌, 스프-폴리에틸렌`); this table states
    it per part (`면-폴리프로필렌`, `분말스프-폴리에틸렌`). Measured on the 1,838
    products both cover, only 163 (8.9 %) are the same string once whitespace and
    commas are dropped - so the report keeps its column and the label gets these
    rows, and neither is rewritten from the other.
    """

    __tablename__ = "food_label_packaging"
    __table_args__ = (
        UniqueConstraint(
            "source", "label_key", "position", name="uq_food_label_packaging_natural_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(NAME_LENGTH))
    label_key: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    position: Mapped[int] = mapped_column(Integer)
    packaging_text: Mapped[str | None] = mapped_column(Text, default=None)

    # The label that printed it - a logical join, never a foreign key: both
    # sides are rebuilt whole by the derive job, and a constraint would make the
    # order of two independent rebuilds a correctness question.
    # Measured 2026-09-13: 6,914 rows over 3,809 라벨, of which 2,278 have a
    # 표시사항 row - the packaging feed is the wider one, so 1,531 labels exist
    # here as their 푸드QR key with the columns the 표시사항 feed would have filled
    # left NULL.
    label: Mapped[FoodLabel | None] = relationship(
        primaryjoin=lambda: (
            (foreign(FoodLabelPackaging.source) == FoodLabel.source)
            & (foreign(FoodLabelPackaging.label_key) == FoodLabel.label_key)
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
