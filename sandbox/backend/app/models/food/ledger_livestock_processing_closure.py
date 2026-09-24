# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Constants
# ============================================================

# 인허가번호 is 11 characters on every row; the parcel and building keys of the
# GIS feed reach 19 and 28. The same bound the sibling ledgers use.
CODE_LENGTH = 32

# YYYYMMDD.
DATE_LENGTH = 16

# The closed vocabularies - 업종 (17 characters at the widest), 폐업구분 (8),
# 소재지 (구 단위, 18), 관할기관명 (15). 업소명 is free text and goes to `Text`.
NAME_LENGTH = 120

# 산 여부 - one character.
FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodLedgerLivestockProcessingClosure(Base, AuditMixin):
    """축산물 가공업 폐업정보 원장 - our own copy of the I2824 file.

    One row per 인허가번호. 8,071 rows in the file of 2026-09-23 (gzip 0.2MB), every column filled
    but the ones the schema declines (`UNSTORED_KEYS`). 축산물가공업 3업종(식육 7,336 · 유 457 ·
    알 278)의 폐업 인허가. I2500 과 겹치지 않는다 — 0/8,071.
    """

    __tablename__ = "food_ledger_livestock_processing_closure"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    license_no: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    industry_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    permit_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    closed_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    closure_kind: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    district: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    institution_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
