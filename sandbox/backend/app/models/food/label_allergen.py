# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import Index, Integer, String, UniqueConstraint, Uuid
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

SYNCED_COLUMNS = ("name",)


# ============================================================
# Classes
# ============================================================


class FoodLabelAllergen(Base, AuditMixin):
    """One allergen a label declares, as the manufacturer wrote it.

    Derived from two feeds. 푸드QR answers one row per declared allergen already
    (8,580 rows over 1,746 라벨, 8,441 distinct label-name pairs); HACCP answers
    one comma-joined string per product, of which **8,484 of 14,664 read
    `알수없음` and 41 read `없음`** - those become no row at all, which is the
    whole difference from revision 171's split, where 30 % of the values were
    that word.

    Splitting HACCP's string yields 19,802 rows over 6,115 products and 379
    distinct names against 푸드QR's 74 (measured 2026-09-13). The names are kept
    as written: `소고기` is not folded into `쇠고기`, `난류` not into `알류`.
    Normalising a declared allergen onto the 22 법정 names would be this
    harness making a safety claim the package did not.
    """

    __tablename__ = "food_label_allergen"
    __table_args__ = (
        UniqueConstraint(
            "source", "label_key", "position", name="uq_food_label_allergen_natural_key"
        ),
        Index("ix_food_label_allergen_name", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(NAME_LENGTH))
    label_key: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)

    # The label that printed it - a logical join, never a foreign key: both
    # sides are rebuilt whole by the derive job, and a constraint would make the
    # order of two independent rebuilds a correctness question.
    # Measured 2026-09-13 over both feeds: 8,441 푸드QR rows and 19,802 HACCP
    # rows, all of which carry a label row here because the label table is built
    # from the same two passes.
    label: Mapped[FoodLabel | None] = relationship(
        primaryjoin=lambda: (
            (foreign(FoodLabelAllergen.source) == FoodLabel.source)
            & (foreign(FoodLabelAllergen.label_key) == FoodLabel.label_key)
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
