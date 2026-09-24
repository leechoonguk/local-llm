# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ============================================================
# Constants
# ============================================================

# Which ledger a row came from - the live master or a closure feed. The two
# are disjoint by 인허가번호 (measured 2026-09-23), so the pair is closed and a
# filter can be a select of two.
BusinessStatus = Literal["ACTIVE", "CLOSED"]


# ============================================================
# Classes
# ============================================================


class FoodBusinessBase(BaseModel):
    """One licensed food business as the derived table holds it.

    Read-only over HTTP: the table is rebuilt whole by the derive job every
    night (rule://backend-ledger), so there is no Create or Update request.
    """

    model_config = ConfigDict(extra="forbid")

    license_no: str
    industry_name: str | None = None
    business_name: str | None = None
    permit_date: str | None = None
    district: str | None = None
    status: BusinessStatus
    closed_date: str | None = None
    closure_kind: str | None = None
    institution_name: str | None = None
    site_key: str | None = None
    name_key: str | None = None


class FoodBusinessReadResponse(FoodBusinessBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class FoodBusinessDetailReadResponse(FoodBusinessReadResponse):
    """The business with the rows it shares a name or a site with.

    Neither list is a claim of one owner: `same_name` is every other row
    written under the same name key (`우리식품` holds 164 across 100 districts),
    `same_site` every other licence on the same building or parcel.
    """

    same_name: list[FoodBusinessReadResponse]
    same_site: list[FoodBusinessReadResponse]


class FoodBusinessFilter(BaseModel):
    """What a list may be narrowed by - the query parameters, as one object.

    Free text (name, number, district) matches a fragment; the industry is
    picked from `FoodBusinessFacets` and matched whole; the status is the pair
    the schema closes.
    """

    model_config = ConfigDict(extra="forbid")

    business_name: str | None = None
    license_no: str | None = None
    district: str | None = None
    industry_name: str | None = None
    status: BusinessStatus | None = None


class FoodBusinessFacets(BaseModel):
    """The closed vocabulary the industry select offers - the table's own values.

    Ten industries in the live pass of 2026-09-23; read from the rows so a
    value the portal adds arrives the night it appears.
    """

    model_config = ConfigDict(extra="forbid")

    industry_name: list[str]


# ============================================================
# Functions
# ============================================================


def to_read(business: object) -> FoodBusinessReadResponse:
    return FoodBusinessReadResponse.model_validate(business)


def to_read_list(businesses: Sequence[object]) -> list[FoodBusinessReadResponse]:
    return [to_read(business) for business in businesses]
