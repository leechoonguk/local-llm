# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Constants
# ============================================================

# A sha256 in hex. Not a provider value: this feed publishes no identifier, so
# the key is computed from the record itself (see `record_digest`).
DIGEST_LENGTH = 64

# 수거일자 8 (YYYYMMDD), 품목제조보고번호 19 - both bounded by their format, not
# by a case. Measured over the whole feed (2,046,194 rows, 2026-09-18).
CODE_LENGTH = 32

# The closed vocabularies: 검체구분 11 자 at its widest (축산물(축산물가공품)),
# 업종 17, 판정결과 5 (상기와같음). 최종수정일시 arrives as text
# ("2026-09-18 16:25:59.676351"), 26 자. The 검체구분 vocabulary is wider than
# its own request codes document: 환경검체 appears on 395 rows and is none of the
# ten codes `TKAWYSPCI_TYPECD` accepts.
NAME_LENGTH = 120

# Free text is `Text`: 제품명 122, 업소명 57, 수거계획명 54, 수행기관명 36,
# 수거증번호 30, 소재지 24 - measured over the whole feed, and every one of them
# grows with the case rather than with a format. A `String(n)` here would be a
# guess that fails on the row that outgrows it, at the one moment nobody is
# watching: window 1,400 of a nightly pass.


# ============================================================
# Classes
# ============================================================


class FoodLedgerCollectionInspection(Base, AuditMixin):
    """수거검사 원장 - our own copy of 식품안전나라 I0460, and the largest feed we read.

    One row per specimen collected and judged: 2,046,194 of them, spanning
    수거일자 20000214~20260917 - twenty-six years, not this year.
    **This is the only feed that says a product was found unfit without a
    recall following.** 회수·판매중지 (I0490, 379 rows) lists what was recalled
    and 검사부적합 (I2620, 593) what was announced; a 부적합 that led to neither
    is here alone.

    The judgments, over the whole feed: 적합 68.3 %, 공백 21.1 % (not yet
    published), 상기와같음 5.4 %, 검토중 4.7 %, **부적합 0.43 %**. That last
    figure is why the whole feed earns its cost: the 8,861 rows it amounts to
    are published nowhere cheaper, and the portal's `JDGMNT_CD_NM` filter is
    accepted and ignored.

    **This feed has no key, so we mint one.** 수거증번호 repeats 651,739 times
    (1,394,455 distinct over 2,046,194 rows), and so does every composite of the
    published columns. The response omits whatever tells two specimens of one
    수거증 apart - 검사항목 is not among the twelve columns. Even the whole record
    repeats: 1,037 rows of the portal's own single-file snapshot are identical
    in all twelve values, so this is the publisher repeating itself and not a
    walk seeing a row twice. `record_digest` - a sha256 of all twelve values -
    is therefore the natural key: two rows identical in every published column
    say the same thing, and collapsing them loses nothing a reader could have
    seen.

    `item_report_no` (품목제조보고번호) is the one column that reaches a product,
    and it is filled on 32.6 % of rows - so it is indexed and it is nullable.
    A 수거 of 농산물 or of a 집단급식소's tap water has no 품목보고 and is still a
    record. 업소명 is empty on 40.8 % and 업종 on 44.5 % for the same reason.
    """

    __tablename__ = "food_ledger_collection_inspection"
    __table_args__ = (
        UniqueConstraint("record_digest", name="uq_food_ledger_collection_inspection_natural_key"),
        Index("ix_food_ledger_collection_inspection_item_report_no", "item_report_no"),
        Index("ix_food_ledger_collection_inspection_judgment", "judgment"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    record_digest: Mapped[str] = mapped_column(String(DIGEST_LENGTH))
    collection_no: Mapped[str | None] = mapped_column(Text, default=None)
    product_name: Mapped[str | None] = mapped_column(Text, default=None)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    address: Mapped[str | None] = mapped_column(Text, default=None)
    industry_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    specimen_type: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    collected_on: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    judgment: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    institution_name: Mapped[str | None] = mapped_column(Text, default=None)
    item_report_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    plan_title: Mapped[str | None] = mapped_column(Text, default=None)
    source_updated_text: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
