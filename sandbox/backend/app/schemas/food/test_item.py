# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.mfds_source import source_text, source_updated_at
from app.models.food.test_item import FoodTestItem


# ============================================================
# Constants
# ============================================================

CODE_MAX_LENGTH = 32

CODE_LENGTH = 32

NAME_LENGTH = 120

FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodTestItemMutable(BaseModel):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-test-item`).
    """

    model_config = ConfigDict(extra="forbid")

    korean_name: str | None = None
    english_name: str | None = None
    abbreviation: str | None = None
    alias: str | None = None
    test_item_name: str | None = None
    major_class_sequence: str | None = Field(default=None, max_length=CODE_LENGTH)
    major_class_code: str | None = Field(default=None, max_length=CODE_LENGTH)
    major_class_korean_name: str | None = Field(default=None, max_length=NAME_LENGTH)
    middle_class_sequence: str | None = Field(default=None, max_length=CODE_LENGTH)
    middle_class_code: str | None = Field(default=None, max_length=CODE_LENGTH)
    middle_class_korean_name: str | None = Field(default=None, max_length=NAME_LENGTH)
    residue_definition: str | None = None
    in_use: str | None = Field(default=None, max_length=FLAG_LENGTH)
    source_updated_at: datetime | None = None


class FoodTestItemBase(FoodTestItemMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    test_item_code: str = Field(max_length=CODE_LENGTH)


class FoodTestItemCreateRequest(FoodTestItemBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodTestItemCreateRequest | None:
        """Map one canonical I2530 record onto the ledger, or refuse it.

        A record with no `test_item_code` cannot be matched by a later pass,
        so it is dropped here rather than becoming a row no merge can find
        again. Every other refusal still raises: that is a contract change,
        not a sparse record.
        """
        test_item_code = source_text(record.get("test_item_code"))
        if test_item_code is None:
            return None
        return cls(
            test_item_code=test_item_code,
            korean_name=source_text(record.get("korean_name")),
            english_name=source_text(record.get("english_name")),
            abbreviation=source_text(record.get("abbreviation")),
            alias=source_text(record.get("alias")),
            test_item_name=source_text(record.get("test_item_name")),
            major_class_sequence=source_text(record.get("major_class_sequence")),
            major_class_code=source_text(record.get("major_class_code")),
            major_class_korean_name=source_text(record.get("major_class_korean_name")),
            middle_class_sequence=source_text(record.get("middle_class_sequence")),
            middle_class_code=source_text(record.get("middle_class_code")),
            middle_class_korean_name=source_text(record.get("middle_class_korean_name")),
            residue_definition=source_text(record.get("residue_definition")),
            in_use=source_text(record.get("in_use")),
            source_updated_at=source_updated_at(record.get("last_updated_at")),
        )


class FoodTestItemCreateInternal(FoodTestItemBase):
    created_by: str


class FoodTestItemReadResponse(FoodTestItemBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    version: int


class FoodTestItemUpdateRequest(FoodTestItemMutable):
    """Every column except the natural key, which is the row's identity."""


class FoodTestItemUpdateInternal(FoodTestItemUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================


def to_read(item: FoodTestItem) -> FoodTestItemReadResponse:
    return FoodTestItemReadResponse.model_validate(item)


def to_read_list(items: list[FoodTestItem]) -> list[FoodTestItemReadResponse]:
    return [FoodTestItemReadResponse.model_validate(i) for i in items]
