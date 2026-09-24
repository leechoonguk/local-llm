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

# Whether the portal still lists the code - the two values `use_yn` holds
# (`Y` 42,431 - 18,737 retired `N`, measured 2026-09-08), spelled here so a
# reader can switch on it and a filter can be a closed pair.
UseFlag = Literal["Y", "N"]


# ============================================================
# Classes
# ============================================================


class FoodRawMaterialBase(BaseModel):
    """One raw material as the derived table holds it - I2520 read down to what food is made of.

    Read-only over HTTP: the table is rebuilt whole by the derive job every
    night (rule://backend-ledger), so there is no Create or Update request -
    a row written by hand would be gone by morning.
    """

    model_config = ConfigDict(extra="forbid")

    raw_material_code: str
    base_code: str
    representative_raw_material_name: str | None = None
    raw_material_alias: str | None = None
    english_name: str | None = None
    scientific_name: str | None = None
    raw_material_large_class: str | None = None
    raw_material_medium_class: str | None = None
    region_code_name: str | None = None
    process_code_name: str | None = None
    raw_material_status_code_name: str | None = None
    use_yn: str | None = None
    source_updated_at: datetime | None = None


class FoodRawMaterialReadResponse(FoodRawMaterialBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class FoodRawMaterialDetailReadResponse(FoodRawMaterialReadResponse):
    """The material with its composition's siblings - the same base's codes, itself included."""

    variants: list[FoodRawMaterialReadResponse]


class FoodRawMaterialFilter(BaseModel):
    """What a list may be narrowed by - the query parameters, as one object.

    Two kinds, and the kind is decided by the column, not the caller: free
    text (the code, the representative name, the alias list) matches a
    fragment; a closed vocabulary (large class, medium class, status) is
    picked from `FoodRawMaterialFacets` and matched whole - `식물` must not
    return `식물성유지`; the use flag is the pair the schema closes.
    """

    model_config = ConfigDict(extra="forbid")

    raw_material_code: str | None = None
    representative_raw_material_name: str | None = None
    raw_material_alias: str | None = None
    raw_material_large_class: str | None = None
    raw_material_medium_class: str | None = None
    raw_material_status_code_name: str | None = None
    use_yn: UseFlag | None = None


class FoodRawMaterialFacets(BaseModel):
    """The closed vocabularies a select filter offers - the table's own distinct values.

    Read from the rows rather than seeded, because the portal owns these
    vocabularies and the sync brings a new value the night it appears; a list
    typed into a screen would offer yesterday's choices. Measured 2026-09-09:
    5 large classes, 17 medium classes, 85 status names.

    **The medium class is a child of the large class**, so it is answered
    twice: flat, for a screen with no large class chosen, and grouped by the
    large class each value appears under (20 pairs), so choosing
    `식품원료(A코드)` narrows the medium select to its own. A value may appear
    under more than one parent - the groups are the rows' truth, not a tree
    someone drew.
    """

    model_config = ConfigDict(extra="forbid")

    raw_material_large_class: list[str]
    raw_material_medium_class: list[str]
    raw_material_medium_class_by_large: dict[str, list[str]]
    raw_material_status_code_name: list[str]


# ============================================================
# Functions
# ============================================================


def to_read(material: object) -> FoodRawMaterialReadResponse:
    return FoodRawMaterialReadResponse.model_validate(material)


def to_read_list(materials: Sequence[object]) -> list[FoodRawMaterialReadResponse]:
    return [to_read(material) for material in materials]
