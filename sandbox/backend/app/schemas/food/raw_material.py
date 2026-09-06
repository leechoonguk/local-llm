# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.mfds_source import source_text, source_updated_at
from app.models.food.raw_material import FoodRawMaterial


# ============================================================
# Constants
# ============================================================

CODE_MAX_LENGTH = 32

# Provider free text — the columns are String(200) for the same reason.
NAME_MAX_LENGTH = 200

CLASSIFICATION_NAME_MAX_LENGTH = 120

# `YYYYMMDD` as the portal sends it, with room for the dashed form a sibling
# service of the same portal uses for the same concept.
DATE_TEXT_MAX_LENGTH = 20

USE_FLAG_MAX_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodRawMaterialMutable(BaseModel):
    """Every column a sync may refresh — the record minus its identity.

    Declared once and inherited twice: `FoodRawMaterialBase` adds the natural
    key to it, `FoodRawMaterialUpdateRequest` is it. Written out in both places
    instead, the two lists were 24 identical lines that a new column has to be
    added to twice — and the day one of them is missed, the sync stops
    refreshing a column nobody notices until the ledger disagrees with the
    portal.

    The field names are the operation's canonical response keys
    (`search-food-raw-material`), so a record the client returns maps into this
    model without a translation table — one concept, one key, from the wire
    through the ledger.
    """

    model_config = ConfigDict(extra="forbid")

    representative_raw_material_name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    # Unbounded on purpose: these three are synonym *lists* the portal joins
    # into one string (measured over the whole feed, 2026-09-05: 1130/272/311
    # characters), and their columns are `Text`. A bound here would reject a
    # record the ledger can store — and a rejection fails the whole page.
    raw_material_alias: str | None = None
    english_name: str | None = None
    scientific_name: str | None = None
    raw_material_large_class: str | None = Field(
        default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH
    )
    raw_material_medium_class: str | None = Field(
        default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH
    )
    region_code: str | None = Field(default=None, max_length=CODE_MAX_LENGTH)
    region_code_name: str | None = Field(default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH)
    process_code: str | None = Field(default=None, max_length=CODE_MAX_LENGTH)
    process_code_name: str | None = Field(default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH)
    raw_material_status_code: str | None = Field(default=None, max_length=CODE_MAX_LENGTH)
    raw_material_status_code_name: str | None = Field(
        default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH
    )
    valid_start_date: str | None = Field(default=None, max_length=DATE_TEXT_MAX_LENGTH)
    valid_end_date: str | None = Field(default=None, max_length=DATE_TEXT_MAX_LENGTH)
    use_yn: str | None = Field(default=None, max_length=USE_FLAG_MAX_LENGTH)
    source_updated_at: datetime | None = None


class FoodRawMaterialBase(FoodRawMaterialMutable):
    """The mutable columns plus the one that identifies the row."""

    raw_material_code: str = Field(max_length=CODE_MAX_LENGTH)


class FoodRawMaterialCreateRequest(FoodRawMaterialBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodRawMaterialCreateRequest | None:
        """Map one canonical I2520 record onto the ledger, or refuse it.

        A record with no `raw_material_code` cannot be upserted — the next
        window would insert it a second time — so it is dropped here instead of
        becoming a row no sync can ever match again. Every other refusal (a name
        past its column bound) still raises: that is a contract change, not a
        sparse record.
        """
        raw_material_code = source_text(record.get("raw_material_code"))
        if raw_material_code is None:
            return None
        return cls(
            raw_material_code=raw_material_code,
            representative_raw_material_name=source_text(
                record.get("representative_raw_material_name")
            ),
            raw_material_alias=source_text(record.get("raw_material_alias")),
            english_name=source_text(record.get("english_name")),
            scientific_name=source_text(record.get("scientific_name")),
            raw_material_large_class=source_text(record.get("raw_material_large_class")),
            raw_material_medium_class=source_text(record.get("raw_material_medium_class")),
            region_code=source_text(record.get("region_code")),
            region_code_name=source_text(record.get("region_code_name")),
            process_code=source_text(record.get("process_code")),
            process_code_name=source_text(record.get("process_code_name")),
            raw_material_status_code=source_text(record.get("raw_material_status_code")),
            raw_material_status_code_name=source_text(record.get("raw_material_status_code_name")),
            valid_start_date=source_text(record.get("valid_start_date")),
            valid_end_date=source_text(record.get("valid_end_date")),
            use_yn=source_text(record.get("use_yn")),
            source_updated_at=source_updated_at(record.get("last_update_datetime")),
        )


class FoodRawMaterialCreateInternal(FoodRawMaterialBase):
    created_by: str


class FoodRawMaterialReadResponse(FoodRawMaterialBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class FoodRawMaterialUpdateRequest(FoodRawMaterialMutable):
    """Every column except the natural key, which is the row's identity.

    Repointing `raw_material_code` would silently move a material's history onto
    another one; the sync inserts the new code instead. That is not a rule this
    class states in prose — it is the one field it does not inherit.
    """


class FoodRawMaterialUpdateInternal(FoodRawMaterialUpdateRequest):
    updated_by: str


class FoodRawMaterialFilter(BaseModel):
    """What narrows a page of the ledger - one field per box on the screen.

    Two kinds, and the kind is decided by the column, not the caller:

    - **contains** on free text (`raw_material_code`, the representative name,
      the alias list) - a reader types a fragment.
    - **equals** on a closed vocabulary (large class, medium class, status) - a
      reader picks one of the column's own values, offered by
      `FoodRawMaterialFacets`. Matched whole: `식물` must not return `식물성유지`.

    The fields are the query parameters' names, so the page and its count are
    narrowed by one object and cannot disagree.
    """

    model_config = ConfigDict(extra="forbid")

    raw_material_code: str | None = None
    representative_raw_material_name: str | None = None
    raw_material_alias: str | None = None
    raw_material_large_class: str | None = None
    raw_material_medium_class: str | None = None
    raw_material_status_code_name: str | None = None


class FoodRawMaterialFacets(BaseModel):
    """The closed vocabularies a select filter offers - the ledger's own distinct values.

    Read from the rows rather than seeded, because the portal owns these
    vocabularies and the sync brings a new value the night it appears; a list
    typed here would offer yesterday's choices. Measured (2026-09-05): 7 large
    classes, 30 medium classes, 85 status names.

    **The medium class is a child of the large class**, so it is answered twice:
    flat, for a screen with no large class chosen, and grouped by the large
    class each value appears under, so choosing `식품원료(A코드)` narrows the
    medium select to its own seven. Measured: every medium class sits under one
    large class except `한시적인정`, which two share - a value may therefore
    appear in more than one group, and the groups are the rows' truth, not a
    tree someone drew.
    """

    model_config = ConfigDict(extra="forbid")

    raw_material_large_class: list[str]
    raw_material_medium_class: list[str]
    raw_material_medium_class_by_large: dict[str, list[str]]
    raw_material_status_code_name: list[str]


# ============================================================
# Functions
# ============================================================


def to_read(material: FoodRawMaterial) -> FoodRawMaterialReadResponse:
    return FoodRawMaterialReadResponse.model_validate(material)


def to_read_list(materials: list[FoodRawMaterial]) -> list[FoodRawMaterialReadResponse]:
    return [FoodRawMaterialReadResponse.model_validate(i) for i in materials]
