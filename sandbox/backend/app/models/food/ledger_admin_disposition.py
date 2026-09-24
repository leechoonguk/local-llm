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

# 행정처분전산키 7, 인허가번호 11, 처분일자 8 - measured over the whole feed
# (251 rows, 2026-09-18), the same bound as every sibling ledger of this portal.
CODE_LENGTH = 32

# The closed vocabularies: 처분유형 13 자 at the widest (영업정지 및 해당제품폐기),
# 업종 11, 처분기관명 14. 공개기한 and 최종수정일 arrive as text ("2026-10-03
# 00:00:00.0", "2026-09-18 01:40:19.181"), 21 and 23 자.
NAME_LENGTH = 120

# Free text - 위반내용 623, 위반법령 137, 처분내용 111 - is `Text`: none of the
# three is a vocabulary the portal closes, and the longest grows with the case.


# ============================================================
# Classes
# ============================================================


class FoodLedgerAdminDisposition(Base, AuditMixin):
    """행정처분 원장 - our own copy of 식품안전나라 I0480 (식품제조가공업).

    One row per administrative disposition: 251 rows over the whole feed
    (2026-09-18), one window of the RANGE walk. `disposition_seq`
    (행정처분전산키) is distinct on every one of them and never empty, so it
    alone is the natural key. The data.go.kr mirror of the same dataset carries
    three duplicate keys in 254 rows; this portal's does not.

    **The subject is the business, not a product.** No column names a 제품 or a
    품목제조보고번호, so this ledger answers "is the maker of this product under
    a disposition" and never "what happened to this product". The join is
    `license_no` (인허가번호), which `food_item_report` carries on 1,688,015 of
    its 1,980,742 rows (85.2 %) - which is why it is indexed here.

    Two columns the portal publishes and never fills: `telephone` and
    `president_name` are "" on all 251 rows. They are kept because the column
    exists on the wire and a row that starts carrying one is not a contract
    change.
    """

    __tablename__ = "food_ledger_admin_disposition"
    __table_args__ = (
        UniqueConstraint("disposition_seq", name="uq_food_ledger_admin_disposition_natural_key"),
        Index("ix_food_ledger_admin_disposition_license_no", "license_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    disposition_seq: Mapped[str] = mapped_column(String(CODE_LENGTH))
    license_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    industry_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    # 처분확정일자 / 처분시작일 / 처분종료일, all YYYYMMDD on the wire. Kept as
    # text like every date of this portal: 처분종료일 is "-" whenever the
    # disposition is not a suspension (영업허가·등록취소, 과징금).
    decided_on: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None, index=True)
    began_on: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    ended_on: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    disposition_type: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    violation_text: Mapped[str | None] = mapped_column(Text, default=None)
    disposition_text: Mapped[str | None] = mapped_column(Text, default=None)
    law_text: Mapped[str | None] = mapped_column(Text, default=None)
    address: Mapped[str | None] = mapped_column(Text, default=None)
    telephone: Mapped[str | None] = mapped_column(Text, default=None)
    president_name: Mapped[str | None] = mapped_column(Text, default=None)
    institution_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    public_until: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    source_updated_text: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
