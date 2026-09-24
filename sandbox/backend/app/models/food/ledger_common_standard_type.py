# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

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


# ============================================================
# Classes
# ============================================================


class FoodLedgerCommonStandardType(Base, AuditMixin):
    """공통기준종류 원장 - our own copy of the I2590 records.

    One row per 공통기준 group, keyed by `common_standard_type_code`: the
    tree (`parent_common_standard_type_code`, `level`) of the 식품공전 chapters
    that the 공통기준규격 rows of `food_ledger_common_standard` (I2600) point at
    through the same code. The smallest of the four 기준규격 ledgers, and the
    one the other three are read against.

    Measured 2026-09-07 over the whole feed (90 rows): the code is unique,
    never empty, and the columns are the portal's 7-field list. Two group
    codes I2600 points at (000165 with 15,794 rows, 000136 with 12) are not
    here - `food_ledger_common_standard.common_standard_type_code` is a value join,
    and those rows read as parentless.

    `source_updated_at` is the provider's `LAST_UPDT_DTM` (KST, 2014-12-02 ..
    2026-05-26 on the measured feed), a reading of when the portal last touched the
    row; the pass walks the whole feed.
    """

    __tablename__ = "food_ledger_common_standard_type"
    __table_args__ = (
        Index("ix_food_ledger_common_standard_type_source_updated_at", "source_updated_at"),
        # `common_standard_type_` said once: the derived name repeats it and reaches
        # 68 characters, and PostgreSQL truncates an identifier at 63 silently.
        Index(
            "ix_food_ledger_common_standard_type_parent_code",
            "parent_common_standard_type_code",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    common_standard_type_code: Mapped[str] = mapped_column(
        String(CODE_LENGTH), unique=True, index=True
    )
    standard_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    parent_common_standard_type_code: Mapped[str | None] = mapped_column(
        String(CODE_LENGTH), default=None
    )
    level: Mapped[str | None] = mapped_column(String(LEVEL_LENGTH), default=None)
    definition: Mapped[str | None] = mapped_column(Text, default=None)
    use_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
