# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


# ============================================================
# Constants
# ============================================================

# 인허가번호 is 11 characters on every row of every source; the site keys the GIS
# ledger answers reach 28. The same bound the ledgers use.
CODE_LENGTH = 32

# YYYYMMDD.
DATE_LENGTH = 16

# The closed vocabularies - 업종 (17 characters at the widest), 폐업구분 (8),
# 소재지 (구 단위, 18), 관할기관명 (15). 업소명 and its key are free text.
NAME_LENGTH = 120

# The two states a licence is in. A licence is in the live master or in one of
# the closure feeds and never both (measured 2026-09-23: 0 of 546,122 closed
# 인허가번호 also in I2500), so the state is which ledger the row came from.
ACTIVE = "ACTIVE"

CLOSED = "CLOSED"

STATUS_LENGTH = 8

# What identifies a row across rebuilds: the 인허가번호, one per business.
# Listed on the model because nothing but the derive job writes this table.
NATURAL_KEY = ("license_no",)


# ============================================================
# Classes
# ============================================================


class FoodBusiness(Base, AuditMixin):
    """One licensed food business - manufacturer, processor or importer - live or closed.

    Derived, not fed: the derive job rebuilds it off eight ledgers. The live
    rows are the ten industries this project reads out of the 52 the 인허가
    업소 master (I2500) carries - 식품제조가공업 and its 주류 variant, 식품첨가물
    제조업, 건강기능식품 전문·벤처제조업, the three 축산물가공업, 식육포장처리업,
    수입식품등 수입판매업: 96,367 of 1,549,221 (live pass, 2026-09-23). The closed
    rows are the same industries out of the six closure feeds: 202,652 - 61,833
    + 917 제조, 1,708 첨가물, 119,759 수입판매, 493 건기식 제조, 8,072 축산가공,
    9,870 식육포장.

    The unit is the 인허가, not the corporation - a corporation with several
    factories holds several rows, and nothing public keys them together
    (measured 2026-09-23: no MFDS, LOCALDATA or 국민연금 dataset carries a
    법인등록번호 beside a licence). `name_key` is the name with its corporate
    suffixes and spaces removed, so a screen can list the rows of one name;
    it is a candidate list, never a claim of one owner (`우리식품` holds 28
    licences under different owners). `site_key` is the building or parcel
    the GIS ledger answers for 21.7 % of the live rows (2,019 sites hold more
    than one licence), where two licences of
    one factory - 제조 and 축산가공 on one site - share a value.

    What the registries key on this: `food_item_report.license_no` resolves
    100.0 % (31,244 of 31,255 licences, live masters alone), the production
    ledgers 95.1 % / 100.0 % with the closures in; the import ledger carries
    only a name and resolves through `name_key` (98.3 % of rows, 12.6 % of
    them to several live licences).
    """

    __tablename__ = "food_business"
    __table_args__ = (
        Index("ix_food_business_name_key", "name_key"),
        Index("ix_food_business_industry_name", "industry_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    license_no: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True)
    industry_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    business_name: Mapped[str | None] = mapped_column(Text, default=None)
    permit_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    district: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    # Computed: which ledger the row came from - ACTIVE from I2500, CLOSED from
    # a closure feed.
    status: Mapped[str] = mapped_column(String(STATUS_LENGTH))
    # The closure feed's own three columns; NULL on a live row.
    closed_date: Mapped[str | None] = mapped_column(String(DATE_LENGTH), default=None)
    closure_kind: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    institution_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), default=None)
    # Computed: the GIS ledger's building number, else its parcel code, else
    # NULL - the key two licences on one site share.
    site_key: Mapped[str | None] = mapped_column(String(CODE_LENGTH), default=None)
    # Computed: `business_name` without spaces, brackets and corporate
    # suffixes (주식회사 · (주) · ㈜ · 유한회사) - what the import ledger's
    # `importer_name` is matched on.
    name_key: Mapped[str | None] = mapped_column(Text, default=None)
