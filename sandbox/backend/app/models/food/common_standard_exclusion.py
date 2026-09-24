# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.food.common_standard_type import FoodCommonStandardType
from app.models.food.product_classification import FoodProductClassification
from app.models.food.test_item import FoodTestItem


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

# What identifies a row across passes, and the columns the derivation fills
# beside it - the ledger's own, one for one. Listed on the model because nothing
# but the derive job writes this table.
NATURAL_KEY = ("common_standard_type_code", "product_code", "test_item_code")


# ============================================================
# Classes
# ============================================================


class FoodCommonStandardExclusion(Base, AuditMixin):
    """One exemption from a 공통기준규격 - a node, a standard type and a test item it spares.
    Derived, not fed: no portal operation answers this table. The derive job
    rebuilds it off the I2610 ledger whole. Measured 2026-09-08: 21 rows under 8
    codes, every one a *tier* of the classification tree (`product_yn` = `N`) -
    an exemption is written where the standard is inherited from, so the first
    cut of the derived tree, types only, gave these rows nothing to land on.

    **Not applied by any read yet.** Measured 2026-09-09: the 21 rows name six
    heading codes (`000008` ... `000068`) of which the current outline carries
    none - `3. 냉동식품` is `000161` today - and no (heading, test item) pair of
    theirs matches any of the 57,457 clauses; the nodes they hang on are 원료
    tiers (식물성, 동물성, 심해성어류 ...) and two retired codes, never a type a
    report names. The item report's standards read therefore ignores them
    rather than carry a branch no data reaches. When the 원료 standards read
    arrives, map the headings by name and apply them there.
    """

    __tablename__ = "food_common_standard_exclusion"

    __table_args__ = (
        UniqueConstraint(
            "common_standard_type_code",
            "product_code",
            "test_item_code",
            name="uq_food_common_standard_exclusion_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    common_standard_type_code: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    product_code: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    test_item_code: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    standard_name: Mapped[str | None] = mapped_column(Text, default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # The tier the exemption is written on: 8 of 8 codes resolve (2026-09-08).
    classification: Mapped[FoodProductClassification | None] = relationship(
        primaryjoin=lambda: (
            foreign(FoodCommonStandardExclusion.product_code)
            == FoodProductClassification.product_code
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
    # The heading the exemption names, by the code I2610 sends: 0 of 21 resolve
    # (2026-09-09) - the codes are an older outline's, and the current one names
    # the same headings under other codes (`3. 냉동식품` is `000161` today).
    standard_type: Mapped[FoodCommonStandardType | None] = relationship(
        primaryjoin=lambda: (
            foreign(FoodCommonStandardExclusion.common_standard_type_code)
            == FoodCommonStandardType.common_standard_type_code
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
    # The test item the exemption spares: 21 of 21 resolve (2026-09-08).
    test_item: Mapped[FoodTestItem | None] = relationship(
        primaryjoin=lambda: (
            foreign(FoodCommonStandardExclusion.test_item_code) == FoodTestItem.test_item_code
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
