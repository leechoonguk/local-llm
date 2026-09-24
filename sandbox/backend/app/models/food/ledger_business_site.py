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


class FoodLedgerBusinessSite(Base, AuditMixin):
    """영업소재지 GIS 코드 원장 - our own copy of the I2560 file.

    One row per 인허가번호. 1,545,751 rows in the file of 2026-09-23 (gzip 46.3MB), every column
    filled but the ones the schema declines (`UNSTORED_KEYS`). 인허가 업소의 부지 키.
    필지(PNU_CD)는 28.6%, 건물관리번호(BDMERGEMANAGENO)는 24.0%만 채워지고 도로명 부분은 전부 빈
    값 — 주소가 구 단위까지만 공개되기 때문. 같은 번호가 두 번 오는 행이 71쌍 있다.
    """

    __tablename__ = "food_ledger_business_site"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    license_no: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    district: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    is_mountain: Mapped[str | None] = mapped_column(String(FLAG_LENGTH), default=None)
    lot_main_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    lot_sub_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    road_district_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    parcel_code: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    building_no: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    ufid: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
