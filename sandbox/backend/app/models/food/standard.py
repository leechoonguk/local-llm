# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.food.common_standard_type import FoodCommonStandardType
from app.models.food.product_classification import FoodProductClassification
from app.models.food.test_item import FoodTestItem


# ============================================================
# Constants
# ============================================================

# Which 공전 chapter the clause is from - the two registries that publish limits
# on food, kept apart by a column rather than by a table because a clause is the
# same fact either way: a test item, a node, a limit, a judgment. `common` is
# 제2 공통기준규격 (I2600, written on 원료 and on tiers of the tree, inherited
# downward); `individual` is 제5 개별기준규격 (I2580, written on one 식품유형).
COMMON_KIND = "common"
INDIVIDUAL_KIND = "individual"
KINDS = (COMMON_KIND, INDIVIDUAL_KIND)

# `individual` (10) is the widest.
KIND_LENGTH = 32

# Every bound below is a whole-feed reading of I2600 (57,457 rows) and I2580
# (16,408 rows), measured 2026-09-07 and 2026-09-15, taken as max(len) per
# column over both feeds.

# `2014000677` (serial, 10), `E0000000000000` (품목, 14), `A30023` (시험항목, 6),
# `01`..`04` (판정·구분 codes), `017` (unit). No code column exceeds 14.
CODE_LENGTH = 32

# Names of closed vocabularies: `SPEC_NM` (group name) is the widest at 107,
# `TESTITM_NM` 28, `PRDLST_CD_NM` 15, the 판정·구분·unit names under 20.
# `FNPRT_ITM_NM` (세부항목명) and `PIAM_KOR_NM` (단서조항명, 206 max) are
# `Text` - the second is a sentence.
NAME_LENGTH = 120

# `20140101` / `99991231` - 8 on every row.
DATE_LENGTH = 20

# `Y`/`N`, and the microbe n/c/m cells (`5`, `0`, `10/50mL` - 7 max) which the
# documentation types as flags of the same width.
FLAG_LENGTH = 20

# `MXMM_VAL`/`MIMM_VAL` stay text: 14 of I2580's 972 distinct non-empty values
# are not decimals - ratios (`15:1`), powers written out (`1.0*10^10`) and three
# carrying a stray U+202C - so a `Numeric` would lose them to a silent None.
VALUE_LENGTH = 120

# What identifies a row across passes, and the columns the derivation fills
# beside it. The four columns after the kind are I2580's own natural key; I2600
# is keyed by two of them and writes the other two empty, so one key serves both
# without collapsing a row of either (measured 2026-09-15: 57,457 and 16,408
# rows, and exactly that many distinct keys on each side).
NATURAL_KEY = ("standard_kind", "standard_seq", "test_item_code", "detail_item_name", "clause_seq")


# ============================================================
# Classes
# ============================================================


class FoodStandard(Base, AuditMixin):
    """One clause of a 기준규격 - a test item's limit on a node of the 공전's tree.

    Derived, not fed: no portal operation answers this table. The derive job
    rebuilds it off the I2600 and I2580 ledgers whole - each ledger's columns
    one for one, no filter - so that the edges below can live here and not on a
    ledger (rule://backend-relations).

    **One table, two chapters.** 공통기준규격 and 개별기준규격 were two tables of
    forty identical columns; what differs between them is where the clause is
    written and therefore how a product reaches it, which is a value
    (`standard_kind`), not a schema. Measured 2026-09-15: 57,457 `common` rows
    under 1,223 codes and 16,408 `individual` rows under 1,763 - 73,865 in all.

    `common_standard_type_code`/`_name` are I2600's alone: 제5 has no headings
    to hang a clause under, and the columns are NULL on every `individual` row.

    A product reaches the two chapters by different roads. 개별: through its
    type, `food_item_report.product_classifications` → these rows - 1,623,968 of
    1,640,212 reports (99.0 %) have at least one. 공통: through that type's
    *ancestors* (a walk up `parent_product_code` at read time - 1,233 rows hang
    on C 가공식품 nodes) and through its 원재료, as the 공전 says (제2-3-7 (2)):
    a processed food's residue limit is its 원료's, which is where 98 % of the
    `common` rows live (잔류농약 35,596 on 851 codes, 동물용의약품 4,319 on 95).

    `product_name` and `test_item_name` are the 공전 registry's own words for
    the node and the item, kept beside the codes rather than read from
    `food_product_classification` and `food_test_item` at query time: they are
    what *this* registry published, and they disagree - 99.8 % of 품목명 and
    96.7 % of 시험항목명 match the tree's and the item ledger's (2026-09-15).
    """

    __tablename__ = "food_standard"

    __table_args__ = (
        UniqueConstraint(
            "standard_kind",
            "standard_seq",
            "test_item_code",
            "detail_item_name",
            "clause_seq",
            name="uq_food_standard_natural_key",
        ),
        CheckConstraint(
            "standard_kind IN ('common', 'individual')",
            name="ck_food_standard_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    standard_kind: Mapped[str] = mapped_column(String(KIND_LENGTH), index=True)
    standard_seq: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    test_item_code: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    detail_item_name: Mapped[str] = mapped_column(Text, default="")
    clause_seq: Mapped[str] = mapped_column(String(CODE_LENGTH), default="")
    common_standard_type_code: Mapped[str | None] = mapped_column(
        String(CODE_LENGTH), default=None, index=True
    )
    common_standard_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    product_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    product_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    test_item_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    clause_name: Mapped[str | None] = mapped_column(Text, default=None)
    standard_value: Mapped[str | None] = mapped_column(Text, default=None)
    standard_value_summary: Mapped[str | None] = mapped_column(Text, default=None)
    valid_begin_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    valid_end_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    source_code: Mapped[str | None] = mapped_column(Text, default=None)
    valid_digits: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    judgment_format_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    judgment_format_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    maximum_value: Mapped[str | None] = mapped_column(String(VALUE_LENGTH), default=None)
    maximum_value_type_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    maximum_value_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    minimum_value: Mapped[str | None] = mapped_column(String(VALUE_LENGTH), default=None)
    minimum_value_type_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    minimum_value_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    choice_fit_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    choice_fit_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    choice_unfit_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    choice_unfit_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    microbe_2n: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    microbe_2c: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    microbe_2m: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    microbe_3m: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    detail_item_included_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    hazard_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    priority_inspection_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    monitoring_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    outside_codex_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    self_inspection_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    unit_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    unit_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    update_reason: Mapped[str | None] = mapped_column(Text, default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # The node this clause is written on, by code - a 원료, a tier or a type.
    # Measured 2026-09-15: 1,221 of I2600's 1,223 codes resolve (the two X codes
    # are the portal's own and in no tree) and 1,762 of I2580's 1,763.
    classification: Mapped[FoodProductClassification | None] = relationship(
        primaryjoin=lambda: (
            foreign(FoodStandard.product_code) == FoodProductClassification.product_code
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
    # The heading of the 공전 a `common` clause hangs under: 57 of 59 codes
    # resolve. NULL on every `individual` row - 제5 publishes no headings.
    standard_type: Mapped[FoodCommonStandardType | None] = relationship(
        primaryjoin=lambda: (
            foreign(FoodStandard.common_standard_type_code)
            == FoodCommonStandardType.common_standard_type_code
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
    # What the clause measures: every code of both feeds resolves (830 and
    # 1,034, 2026-09-15).
    test_item: Mapped[FoodTestItem | None] = relationship(
        primaryjoin=lambda: foreign(FoodStandard.test_item_code) == FoodTestItem.test_item_code,
        viewonly=True,
        lazy="raise_on_sql",
    )
