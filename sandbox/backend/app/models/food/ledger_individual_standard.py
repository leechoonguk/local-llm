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

# Every bound below is a whole-feed reading of I2580 (16,401 rows, measured
# 2026-09-07 after 19:00 KST - the service is closed 09:00-19:00, revision
# 122), taken as max(len) per column.

# `2014016354` (serial, 10), `C0309060100000` (품목, 14 on every row of
# food_ledger_product_classification), `C10002` (시험항목, 6 on every row of
# food_ledger_test_item), `2022000003` (단서조항 serial, 10), `01`..`04` (판정·구분
# codes), `034` (unit). No code column exceeds 14.
CODE_LENGTH = 32

# Names of closed vocabularies: `TESTITM_NM` is the widest at 113, `PRDLST_CD_NM`
# 107, the 판정·구분·unit names under 20. `FNPRT_ITM_NM` (세부항목명, 46 max) and
# `PIAM_KOR_NM` (단서조항명, 77 max) are sentences, kept `Text`.
NAME_LENGTH = 120

# `20140101` / `99991231` - 8 on every row (`VALD_END_DT` is 99991231 on all but
# one row, which ends 20261231).
DATE_LENGTH = 20

# `Y`/`N`, and the microbe n/c/m cells (`5`, `0`, `1000`, `10/50mL` - 7 max)
# which the documentation types as flags of the same width.
FLAG_LENGTH = 20

# `MXMM_VAL`/`MIMM_VAL` stay text: 14 of the 972 distinct non-empty values (23
# rows) are not decimals - ratios (`15:1`, `1.2:1`), powers written out
# (`1.0*10^10`, `1×10^8`, `8×10^10`) and three carrying a stray U+202C - so a
# `Numeric` would lose them to a silent None. Widest is 15.
VALUE_LENGTH = 120


# ============================================================
# Classes
# ============================================================


class FoodLedgerIndividualStandard(Base, AuditMixin):
    """개별기준규격 원장 - our own copy of the I2580 records.

    One row per rule a 품목 carries on its own: a (품목, 시험항목, 세부항목,
    단서조항) with the same rule columns as `food_ledger_common_standard` (I2600)
    minus the group code and name - an individual rule belongs to no 공통기준
    group. `standard_value` (본문) is the rule and `judgment_format_code`
    says which limit columns apply (적/부텍스트, 최대/최소 with their 구분,
    선택형 fit/unfit, 미생물 n/c/m). Judging a 품목 reads this ledger and the
    group rows of `food_ledger_common_standard` that `food_ledger_common_standard_exclusion`
    (I2610) does not strike out.

    The natural key is four columns, not the documented serial: measured
    2026-09-07 (16,401 rows), `INDV_SPEC_SEQ` names 14,138 distinct rules and
    322 of them repeat (up to 17 rows) - one serial per 품목 × 규격 항목, then
    one row per 시험항목, per 세부항목 (`FNPRT_ITM_NM`: a sum rule and its
    component share serial and 시험항목, e.g. 2016003195/B90516 `비스페놀A`
    0.6 vs `` 2.5) and per 단서조항 (`ATTRB_SEQ`: 2017001103/C10002 세균수
    `살균제품에 한한다` 3군법 vs `멸균제품에 한함` 2군법). (seq, 시험항목,
    세부항목) leaves 1 collision and (seq, 시험항목, 단서조항) 4; all four are
    unique. The two name-ish key parts are empty on 14,135 / 14,226 rows, so
    they are stored as "" rather than NULL - a NULL key part never matches on
    the next pass (`schemas.mfds.MfdsKeyText`).

    The two code columns join, by value and without foreign keys (the ledgers
    are replaced independently every night): `product_code` ↔
    `food_ledger_product_classification.product_code`, `test_item_code` ↔
    `food_ledger_test_item.test_item_code`. The names beside them are the portal's
    own copies, kept so a row reads on its own. `source_code` (`SORC`) is not
    a code but the 고시 name (`식품공전(제2022-76호)`, 55 max), hence `Text`.

    `source_updated_at` is the provider's `LAST_UPDT_DTM` (KST, 2020-12-04 ..
    2026-09-04 on the measured feed), a reading of when the portal last touched the
    row; the pass walks the whole feed.
    """

    __tablename__ = "food_ledger_individual_standard"
    __table_args__ = (
        UniqueConstraint(
            "individual_standard_seq",
            "test_item_code",
            "detail_item_name",
            "clause_seq",
            name="uq_food_ledger_individual_standard_natural_key",
        ),
        Index("ix_food_ledger_individual_standard_source_updated_at", "source_updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    individual_standard_seq: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    test_item_code: Mapped[str] = mapped_column(String(CODE_LENGTH), index=True)
    detail_item_name: Mapped[str] = mapped_column(Text, default="")
    clause_seq: Mapped[str] = mapped_column(String(CODE_LENGTH), default="")
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
