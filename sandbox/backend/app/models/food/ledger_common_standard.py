# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Constants
# ============================================================

# Every bound below is a whole-feed reading of I2600 (57,457 rows, measured
# 2026-09-07 after 19:00 KST - the service is closed 09:00-19:00, revision
# 122), taken as max(len) per column.

# `2014000677` (serial, 10), `000080` (group, 6), `E0000000000000` (품목, 14
# on every row of food_ledger_product_classification), `A30023` (시험항목, 6 on
# every row of food_ledger_test_item), `2016000016` (단서조항 serial, 10),
# `01`..`04` (판정·구분 codes), `017` (unit). No code column exceeds 14.
CODE_LENGTH = 32

# Names of closed vocabularies: `SPEC_NM` (group name) is the widest at 107,
# `TESTITM_NM` 28, `PRDLST_CD_NM` 15, the 판정·구분·unit names under 20.
# `FNPRT_ITM_NM` (세부항목명, 10 max) and `PIAM_KOR_NM` (단서조항명, 206 max)
# are `Text` - the second is a sentence.
NAME_LENGTH = 120

# `20140101` / `99991231` - 8 on every row (`VALD_END_DT` is 99991231 on all).
DATE_LENGTH = 20

# `Y`/`N`, and the microbe n/c/m cells (`5`, `0`, `5000000` - 7 max) which
# the documentation types as flags of the same width.
FLAG_LENGTH = 20

# `MXMM_VAL`/`MIMM_VAL` stay text although every one of the 100 distinct
# non-empty values on this feed is a decimal (6 wide at most): the sibling
# I2580 writes the same columns as ratios and powers (`15:1`, `1.0*10^10`),
# and one vocabulary read two ways would lose a value to a silent None the
# day this feed follows it.
VALUE_LENGTH = 120


# ============================================================
# Classes
# ============================================================


class FoodLedgerCommonStandard(Base, AuditMixin):
    """공통기준규격 원장 - our own copy of the I2600 records.

    One row per rule: a (품목, 시험항목, 단서조항) under a 공통기준 group of
    `food_ledger_common_standard_type` (I2590). The rule is `standard_value` (본문)
    and the way it is judged - `judgment_format_code` says which of the
    limit columns apply: 적/부텍스트 reads the text, 최대/최소 read
    `maximum_value` / `minimum_value` with their 구분 (미만·이하), 선택형
    reads the fit/unfit pair (음성/양성), 미생물 reads n/c/m.
    `food_ledger_common_standard_exclusion` (I2610) lists the (품목, 시험항목)
    pairs a group rule does not reach.

    The natural key is (serial, 시험항목), not the documented serial alone:
    measured 2026-09-07 (57,457 rows), `CMMN_SPEC_SEQ` names 57,440 rules and
    16 repeat (3 rows at most) - one serial per 규격 항목, then one row per
    시험항목 it lists (2017016593 보존료: 파라옥시안식향산메틸 B60038, ~에틸
    B60039, and the 적/부 row B60016). `TESTITM_CD` is never empty. Both
    parts are NOT NULL and the pair is unique; the serial keeps a plain index.

    The two code columns join, by value and without foreign keys (the ledgers
    are replaced independently every night): `product_code` ↔
    `food_ledger_product_classification.product_code`, `test_item_code` ↔
    `food_ledger_test_item.test_item_code`. The names beside them are the portal's
    own copies, kept so a row reads on its own. Two measured gaps: the group
    codes 000165 (15,794 rows, name `(1) [별표 6]와 같다`) and 000136 (12) are
    not in I2590, and 109 rows carry X-prefixed 품목 codes that I2510 does
    not list - a join reads them as rows without a parent, not as errors.
    `source_code` (`SORC`) is the 고시 name (`식품공전(제2017-57호,170630)`,
    46 max), hence `Text`.

    `source_updated_at` is the provider's `LAST_UPDT_DTM` (KST, 2020-12-04 ..
    2026-08-18 on the measured feed), a reading of when the portal last touched the
    row; the pass walks the whole feed.
    """

    __tablename__ = "food_ledger_common_standard"
    __table_args__ = (
        UniqueConstraint(
            "common_standard_seq",
            "test_item_code",
            name="uq_food_ledger_common_standard_natural_key",
        ),
        Index("ix_food_ledger_common_standard_source_updated_at", "source_updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    common_standard_seq: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    test_item_code: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    common_standard_type_code: Mapped[str | None] = mapped_column(
        String(CODE_LENGTH), default=None, index=True
    )
    common_standard_type_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    product_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    product_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    test_item_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    detail_item_name: Mapped[str | None] = mapped_column(Text, default=None)
    clause_seq: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
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
