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

SYNCED_COLUMNS = ("caution_text",)


# ============================================================
# Classes
# ============================================================


class FoodLabelCaution(Base, AuditMixin):
    """One 주의사항 문구 a label prints.

    Derived off the 푸드QR 주의사항 ledger, which is the only feed here that
    carries them: 8,134 rows over 2,154 라벨 (2026-09-13), and
    `food_item_report` has no column for any of it.

    1,198 of those rows are the 교차오염 sentence (`…을 사용한 제품과 같은
    제조시설에서 제조하였습니다`). That is a different fact from
    `food_label_allergen`, which is what the product contains, and a reader who
    needs one usually needs the other.
    """

    __tablename__ = "food_label_caution"
    __table_args__ = (
        UniqueConstraint(
            "source", "label_key", "position", name="uq_food_label_caution_natural_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(NAME_LENGTH))
    label_key: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    position: Mapped[int] = mapped_column(Integer)
    caution_text: Mapped[str | None] = mapped_column(Text, default=None)

    # The label that printed it - a logical join, never a foreign key: both
    # sides are rebuilt whole by the derive job, and a constraint would make the
    # order of two independent rebuilds a correctness question.
    # Measured 2026-09-13: all 8,134 rows resolve - the 주의사항 feed knows 2,154
    # 라벨 and the 표시사항 feed 2,278, so every caution has its label.
    label: Mapped[FoodLabel | None] = relationship(
        primaryjoin=lambda: (
            (foreign(FoodLabelCaution.source) == FoodLabel.source)
            & (foreign(FoodLabelCaution.label_key) == FoodLabel.label_key)
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
