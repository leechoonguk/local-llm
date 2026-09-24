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

# `A0100000000000` - 14 characters on every one of the 9,633 records (whole
# feed, 2026-09-06), for the code, its parent and its root alike;
# `attribute_seq` is 10 digits. The same bound as the sibling ledgers.
CODE_LENGTH = 32

# `속성한글명` (`식물성`, `양념`): 23 characters at the widest. The names
# themselves are not bounded - `korean_name` reaches 107 and `english_name`
# 142 - and go to `Text` with the free text below.
NAME_LENGTH = 120

# `20140101` / `99991231` - 8 characters on every measured record.
DATE_LENGTH = 20

# `Y`/`N` flags and the one-digit `level`.
FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodLedgerProductClassification(Base, AuditMixin):
    """식품 품목분류 원장 - our own copy of the I2510 records.

    One row per classification node, keyed by `product_code`. The feed is a
    tree - `level`, `parent_product_code`, `root_product_code` - stored flat,
    in the provider's own codes rather than as a self-referencing foreign
    key: a pass replaces the ledger as a set, and a parent row deleted or
    re-inserted by the overwrite would cascade through a constraint the provider
    itself does not keep (nine level-1 roots have no parent at all; a code
    can name a parent the feed has retired). The codes are the join.

    Small (9,633 rows, ten windows, ~5 s measured 2026-09-06), so it is the
    first feed the provider job walks - a night that runs out of quota still
    finished it. `source_updated_at` is the provider's `LAST_UPDT_DTM`
    (`2021-06-18 11:15:36.860505`), read as KST.
    """

    __tablename__ = "food_ledger_product_classification"
    __table_args__ = (
        Index("ix_food_ledger_product_classification_source_updated_at", "source_updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    product_code: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True)
    level: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    korean_name: Mapped[str | None] = mapped_column(Text, default=None)
    english_name: Mapped[str | None] = mapped_column(Text, default=None)
    definition: Mapped[str | None] = mapped_column(Text, default=None)
    valid_begin_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    valid_end_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    parent_product_code: Mapped[str | None] = mapped_column(
        String(CODE_LENGTH), default=None, index=True
    )
    root_product_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    mixture_product_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    attribute_seq: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    attribute_korean_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    product_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    update_reason: Mapped[str | None] = mapped_column(Text, default=None)
    use_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    remark: Mapped[str | None] = mapped_column(Text, default=None)
    food_group_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    child_favorite_food_yn: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
