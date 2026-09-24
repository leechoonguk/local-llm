# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    and_,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.food import item_report
from app.models.food.item_report import FoodItemReport
from app.models.food.raw_material import FoodRawMaterial


# ============================================================
# Constants
# ============================================================

# The same key as the two ledgers this table is read from: `item_report_no`
# is 13 digits and 16 at the widest (C002, whole feed, 2026-09-06).
CODE_LENGTH = 32

# Which registry a row's report belongs to, in the vocabulary the report table
# owns (`food_item_report`): a row read from C002 is `food` and one read from
# C006 is `livestock`, the same two universes those numbers live in. Imported
# rather than restated so the two derived tables cannot drift into two
# spellings of one word.
KIND_LENGTH = item_report.KIND_LENGTH
DOMESTIC_KIND = item_report.DOMESTIC_KIND
IMPORT_KIND = item_report.IMPORT_KIND
HEALTH_FUNCTIONAL_KIND = item_report.HEALTH_FUNCTIONAL_KIND
LIVESTOCK_KIND = item_report.LIVESTOCK_KIND
KINDS = item_report.KINDS

# What identifies an ingredient row across passes - the slice it belongs to,
# the report, and where the name sat in the report's list - and the two
# columns a pass fills beside it. Listed here and not on a request schema
# because nothing but the two feeds' passes writes this table: a schema
# would be a second statement of two columns.
NATURAL_KEY = ("report_kind", "item_report_no", "position")
SYNCED_COLUMNS = ("ordinal", "name", "material_code", "ingredient_role")


# ============================================================
# Classes
# ============================================================


class FoodItemReportIngredient(Base, AuditMixin):
    """One ingredient of one reported product - the two 원재료 ledgers, split into rows.

    Derived, not fed: no portal operation answers this table. Each pass of
    `food_ledger_item_report_raw_material` (C002) and
    `food_ledger_livestock_item_report_raw_material` (C006) splits the
    `raw_material_names` / `raw_material_ordinals` of the records it is about
    to hold (`services.food.item_report_ingredient._ingredients`, read off the finished
    stage) and writes them over its own `report_kind` slice in the same
    transaction as its ledger (`LedgerStage`, `within`), so the split is
    exactly as old as the ledger it came from and lists what its row lists.
    Measured 2026-09-08 (whole feeds): C002 1,072,302 records → 8,724,566
    rows, 60,521 distinct names, 262 ingredients on the widest product; C006
    567,910 records → 1,411,271 rows, 10,438 names, 105 at the widest.

    `position` is where the name sat in the provider's list, from 1, and is
    what makes the row unique - a product lists the same name twice
    (`당절임, 당절임`). `ordinal` is the provider's 원재료표시순서 paired to
    the name by position, and NULL for every ingredient of a product whose
    two lists differ in length (5,712 C002 rows, 0.5%): the portal's own
    pairing is unknown there, and a guessed one would read as a fact.

    No foreign key to the ledger row: both tables are deleted and refilled
    in one transaction every night, and a constraint between them would only
    dictate the order of the two statements. The join is
    `(report_kind, item_report_no)`, which is the ledger's natural key.
    """

    __tablename__ = "food_item_report_ingredient"
    __table_args__ = (
        UniqueConstraint(
            "report_kind",
            "item_report_no",
            "position",
            name="uq_food_item_report_ingredient_natural_key",
        ),
        CheckConstraint(
            "report_kind IN ('domestic', 'livestock', 'import', 'health_functional')",
            name="ck_food_item_report_ingredient_kind",
        ),
        # "which products name this material": the code first, then the report
        # the row belongs to, so the walk never leaves the index. Measured
        # 2026-09-09 on 밀가루 (94,332 ingredient rows over 87,120 products):
        # with the code indexed alone the planner fetched every matching heap
        # row and spilled its bitmap lossy (34,109 lossy blocks, 1.2s for one
        # page of products); carrying the report's key leaves the heap out.
        Index(
            "ix_food_item_report_ingredient_material_report",
            "material_code",
            "report_kind",
            "item_report_no",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    report_kind: Mapped[str] = mapped_column(String(KIND_LENGTH))
    item_report_no: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    position: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int | None] = mapped_column(Integer, default=None)
    # Free text on the wire (`RAWMTRL_NM` items), indexed because "which
    # products list this name" is the question the split exists to answer.
    name: Mapped[str] = mapped_column(Text, index=True)
    # Which of a registry's lists the name came from. 건강기능식품 publishes three
    # (기능성 원재료 46,084 rows, 기타 원재료 41,764, 캡슐 원재료 12,482, measured
    # 2026-09-15) where the other registries publish one, and the three mean
    # different things - so the row says which it is, and NULL is "the registry
    # sent one list".
    ingredient_role: Mapped[str | None] = mapped_column(String(KIND_LENGTH), default=None)
    # The registry material this name resolves to, decided at write time by
    # the derive job (`item_report_ingredient._resolve`), so the edge is one
    # indexed code join and never a name join over ten million rows. NULL
    # where the name matches no material, or two the rule cannot tell apart.
    material_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    # The report this row was split from. Both columns, because the two
    # registries number their reports in separate spaces and the number alone
    # names a row in each: measured 2026-09-08, all 10,135,735 rows resolve
    # (8,724,566 `food` and 1,411,169 `livestock`, none dangling), which is by
    # construction - a row of a kind is written by that kind's pass, in the
    # transaction that writes the report it came from.
    report: Mapped[FoodItemReport | None] = relationship(
        primaryjoin=lambda: and_(
            foreign(FoodItemReportIngredient.report_kind) == FoodItemReport.report_kind,
            foreign(FoodItemReportIngredient.item_report_no) == FoodItemReport.item_report_no,
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
    # The rule (`services/food/item_report_ingredient._resolve`): the exact
    # name, else the name without its brackets, against the registry's exact
    # names; in use before retired, then class A > B > C > U > P, then the
    # verbatim spelling; a surviving tie is NULL. Measured 2026-09-09 on the
    # rebuilt table: 9,921,636 of 10,129,352 rows carry a code (97.9 %);
    # the 207,716 without are names the registry does not hold (과채가공품,
    # 무수구연산, 5'-리보뉴클레오티드이나트륨) and ties among retired codes.
    material: Mapped[FoodRawMaterial | None] = relationship(
        primaryjoin=lambda: (
            foreign(FoodItemReportIngredient.material_code) == FoodRawMaterial.raw_material_code
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
    # No edge from `name` to the A·B 원료 nodes of the classification tree, by
    # decision (2026-09-09): a product is inspected against its 식품유형's 제5
    # and 제2 clauses, and the 원료 rule (제2-3-7 (2)) is a lab's conversion
    # that needs a 배합비 the report does not carry.
