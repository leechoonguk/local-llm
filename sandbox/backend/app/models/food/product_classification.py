# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base


if TYPE_CHECKING:
    from app.models.food.common_standard_exclusion import FoodCommonStandardExclusion
    from app.models.food.standard import FoodStandard


# ============================================================
# Constants
# ============================================================

# `A0100000000000` - 14 characters on every I2510 record, for the code, its
# parent and its root alike.
CODE_LENGTH = 32

# `속성한글명` (`식물성`, `양념`): 23 characters at the widest. The names
# themselves are not bounded - `korean_name` reaches 107 - and go to `Text`.
NAME_LENGTH = 120

# `20140101` / `99991231` - 8 characters on every measured record.
DATE_LENGTH = 20

# `Y`/`N` flags and the one-digit `level`.
FLAG_LENGTH = 4

# What the pass keeps out of the 9,633 ledger nodes, and why neither kind is in
# the 공전 as it stands (measured 2026-09-08):
#
#   valid_end_date < 99991231 2,412 - retired, most by the 2018 전부개정, which
#                             left 340 of them with `use_yn` still `Y`; their
#                             names are the new tree's names, so keeping them
#                             would put two codes under 빵류
#   product_code LIKE "Z%"    1,071 - 기준규격외 (사료, 화훼, 목재, 농림가공),
#                             outside the 공전 entirely, and it re-lists names
#                             the 공전 also carries (절임식품, 곡류가공품)
#
# The tiers stay (`product_yn` = "N", 212 of the 6,156 that remain): a 공통기준규격
# hangs on a tier and applies to everything under it - 가공식품 (the C root)
# carries 160, 엽경채류 112 - and 102 of the 1,223 codes the common standards
# name are tiers. A report, on the other hand, names a type: `IN_USE` is what
# its edge asks of `product_yn`.
OPEN_ENDED = "99991231"
OUT_OF_CODE_ROOT = "Z"
IN_USE = "Y"

# What identifies a node across passes, and the columns a pass fills beside it.
# Listed here and not on a request schema because nothing but the I2510 pass
# writes this table.
NATURAL_KEY = ("product_code",)
SYNCED_COLUMNS = (
    "level",
    "korean_name",
    "english_name",
    "definition",
    "parent_product_code",
    "root_product_code",
    "product_yn",
    "mixture_product_yn",
    "attribute_korean_name",
    "food_group_yn",
    "child_favorite_food_yn",
    "source_updated_at",
)


# ============================================================
# Classes
# ============================================================


class FoodProductClassification(Base, AuditMixin):
    """The 식품공전's classification tree as it stands - the nodes a report or a standard can name.

    Derived, not fed: no portal operation answers this table. The I2510 pass
    writes it whole in the same transaction as its ledger (`LedgerStage`), and
    what it writes is the ledger minus the retired nodes and the Z root
    (`OPEN_ENDED`, `OUT_OF_CODE_ROOT` above). Measured 2026-09-08: 6,156 of the
    ledger's 9,633 nodes - 5,944 types and 212 tiers - under 5,948 distinct names.

    Two kinds of caller name a node, and they name different kinds. A
    품목제조보고 names a *type* by its Korean name (`product_yn` = `Y`, the lowest
    tier of a branch: 소스 L5 under 소스류 L4), so
    `food_item_report.product_classifications` joins on the name and asks
    `IN_USE`. A 기준규격 names a node by *code*, and a 공통기준규격 names a tier
    on purpose - it applies to everything under it (가공식품 carries 160,
    엽경채류 112; measured 2026-09-08, 102 of its 1,223 codes are tiers). That
    is why the tiers are rows here and not a filter: the first cut of this
    table kept only the types, and the standards' codes had nothing to land on.

    **The filter is here rather than in a join.** Retired and Z nodes re-use the
    living names (빵류 in the 2017 tree and the 2018 one), so every join on a
    name would carry both conditions; written once by the pass, a name here is
    a name in the 공전 as it stands.

    No foreign key to the ledger: both are deleted and refilled by that pass in
    one transaction, and a constraint between them would only dictate the order
    of two statements.
    """

    __tablename__ = "food_product_classification"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    product_code: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True)
    level: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    # Indexed because the name is the only key a 품목제조보고 carries: the report
    # writes 식품유형명, not a code, so this is what the report edge joins on.
    korean_name: Mapped[str | None] = mapped_column(Text, default=None, index=True)
    english_name: Mapped[str | None] = mapped_column(Text, default=None)
    definition: Mapped[str | None] = mapped_column(Text, default=None)
    parent_product_code: Mapped[str | None] = mapped_column(
        String(CODE_LENGTH), default=None, index=True
    )
    root_product_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    # `Y` on a type, `N` on a tier - what tells the two callers' nodes apart.
    product_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    mixture_product_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    attribute_korean_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    food_group_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    child_favorite_food_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # The 개별기준규격 written on this node - a type's own clauses (식품공전 제5).
    # Measured 2026-09-08: 638 of the 755 types the reports name carry some,
    # and 1,623,968 of 1,640,212 reports (99.0 %) reach at least one this way.
    # One table, two chapters: the kind is half of each edge, so the two lists
    # are two filters of `food_standard` rather than two tables.
    # Spelled as strings: the standards import this module (rule://backend-relations).
    individual_standards: Mapped[list[FoodStandard]] = relationship(
        primaryjoin=(
            "and_("
            "FoodProductClassification.product_code == foreign(FoodStandard.product_code), "
            "foreign(FoodStandard.standard_kind) == 'individual'"
            ")"
        ),
        uselist=True,
        viewonly=True,
        lazy="raise_on_sql",
    )
    # The 공통기준규격 written on this node *itself* (제2). Not the ones it inherits:
    # a 공통 clause applies to everything under its node (measured 2026-09-08:
    # 가공식품 root 160 rows, 과자류, 빵류 또는 떡류 13, 과자 3), and the walk up
    # `parent_product_code` is a recursive query at read time, not an edge - 754
    # of the 755 report types reach one within five steps. On a 원료 node (A·B) this list is the
    # residue limits themselves: 소유 317, 닭근육 314.
    common_standards: Mapped[list[FoodStandard]] = relationship(
        primaryjoin=(
            "and_("
            "FoodProductClassification.product_code == foreign(FoodStandard.product_code), "
            "foreign(FoodStandard.standard_kind) == 'common'"
            ")"
        ),
        uselist=True,
        viewonly=True,
        lazy="raise_on_sql",
    )
    # The exemptions written on this node: 8 tiers carry all 21 (2026-09-08).
    common_standard_exclusions: Mapped[list[FoodCommonStandardExclusion]] = relationship(
        primaryjoin=(
            "FoodProductClassification.product_code "
            "== foreign(FoodCommonStandardExclusion.product_code)"
        ),
        uselist=True,
        viewonly=True,
        lazy="raise_on_sql",
    )
