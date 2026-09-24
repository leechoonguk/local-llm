# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import AuditMixin, Base


# ============================================================
# Constants
# ============================================================

# Every bound below is a whole-feed reading of I2590 (90 rows, measured
# 2026-09-07 after 19:00 KST - the service is closed 09:00-19:00, revision
# 122), taken as max(len) per column.

# `000074` - 6 digits on every row; `HRNK_CMMN_SPEC_CD` is the same vocabulary
# (empty on the 3 roots).
CODE_LENGTH = 32

# `SPEC_NM` reaches 107 (`제 2. 공통 기준 및 규격` is the shape; the widest is a
# chapter title with its 고시 number); the name of a 공통기준 group is a title,
# not free text. `DFN` (definition, 20 rows non-empty, 1,236 max) is `Text`.
NAME_LENGTH = 120

# `1`..`8` - the tree depth, deeper than `food_ledger_product_classification.level`
# (1-5 there).
LEVEL_LENGTH = 20

# `Y`/`N`.
FLAG_LENGTH = 20

# What identifies a row across passes, and the columns the derivation fills
# beside it - the ledger's own, one for one. Listed on the model because nothing
# but the derive job writes this table.
NATURAL_KEY = ("common_standard_type_code",)


# ============================================================
# Classes
# ============================================================


class FoodCommonStandardType(Base, AuditMixin):
    """One heading of the 식품공전's table of contents - what a 공통기준규격 is a clause of.

    Derived, not fed: no portal operation answers this table. The derive job
    rebuilds it off the I2590 ledger whole. Measured 2026-09-08: 90 nodes, three
    roots (식품의 기준 및 규격(전부개정), 건강기능식품 고시, 기구 및 용기포장), eight
    levels deep, and the 공전's outline verbatim: 제2 → 3. 식품일반의 기준 및 규격 →
    5) 오염물질 → (2) 중금속 → ① 농산물 ... The 57,457 공통기준규격 rows name 59
    of these; 57 resolve, two (15,790 rows, 동물용의약품 by their rows) name a
    code this ledger does not carry.
    """

    __tablename__ = "food_common_standard_type"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    common_standard_type_code: Mapped[str] = mapped_column(
        String(CODE_LENGTH), unique=True, index=True
    )
    standard_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    parent_common_standard_type_code: Mapped[str | None] = mapped_column(
        String(CODE_LENGTH), default=None, index=True
    )
    level: Mapped[str | None] = mapped_column(String(LEVEL_LENGTH), default=None)
    definition: Mapped[str | None] = mapped_column(Text, default=None)
    use_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # The heading above this one: 87 of 87 non-root nodes resolve (2026-09-08).
    parent: Mapped[FoodCommonStandardType | None] = relationship(
        primaryjoin=lambda: (
            foreign(FoodCommonStandardType.parent_common_standard_type_code)
            == FoodCommonStandardType.common_standard_type_code
        ),
        remote_side=lambda: FoodCommonStandardType.common_standard_type_code,
        viewonly=True,
        lazy="raise_on_sql",
    )
