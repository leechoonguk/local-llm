# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.mfds_source import source_text, source_updated_at
from app.models.food.product_classification import FoodProductClassification


# ============================================================
# Constants
# ============================================================

CODE_MAX_LENGTH = 32

CODE_LENGTH = 32

NAME_LENGTH = 120

DATE_LENGTH = 20

FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodProductClassificationMutable(BaseModel):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-product-classification`).
    """

    model_config = ConfigDict(extra="forbid")

    level: str | None = Field(default=None, max_length=FLAG_LENGTH)
    korean_name: str | None = None
    english_name: str | None = None
    definition: str | None = None
    valid_begin_date: str | None = Field(default=None, max_length=DATE_LENGTH)
    valid_end_date: str | None = Field(default=None, max_length=DATE_LENGTH)
    parent_product_code: str | None = Field(default=None, max_length=CODE_LENGTH)
    root_product_code: str | None = Field(default=None, max_length=CODE_LENGTH)
    mixture_product_yn: str | None = Field(default=None, max_length=FLAG_LENGTH)
    attribute_seq: str | None = Field(default=None, max_length=CODE_LENGTH)
    attribute_korean_name: str | None = Field(default=None, max_length=NAME_LENGTH)
    product_yn: str | None = Field(default=None, max_length=FLAG_LENGTH)
    update_reason: str | None = None
    use_yn: str | None = Field(default=None, max_length=FLAG_LENGTH)
    remark: str | None = None
    food_group_yn: str | None = Field(default=None, max_length=FLAG_LENGTH)
    child_favorite_food_yn: str | None = Field(default=None, max_length=FLAG_LENGTH)
    source_updated_at: datetime | None = None


class FoodProductClassificationBase(FoodProductClassificationMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    product_code: str = Field(max_length=CODE_LENGTH)


class FoodProductClassificationCreateRequest(FoodProductClassificationBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodProductClassificationCreateRequest | None:
        """Map one canonical I2510 record onto the ledger, or refuse it.

        A record with no `product_code` cannot be matched by a later pass, so
        it is dropped here rather than becoming a row no merge can find again.
        Every other refusal still raises: that is a contract change, not a
        sparse record.
        """
        product_code = source_text(record.get("product_code"))
        if product_code is None:
            return None
        return cls(
            product_code=product_code,
            level=source_text(record.get("level")),
            korean_name=source_text(record.get("korean_name")),
            english_name=source_text(record.get("english_name")),
            definition=source_text(record.get("definition")),
            valid_begin_date=source_text(record.get("valid_begin_date")),
            valid_end_date=source_text(record.get("valid_end_date")),
            parent_product_code=source_text(record.get("parent_product_code")),
            root_product_code=source_text(record.get("root_product_code")),
            mixture_product_yn=source_text(record.get("mixture_product_yn")),
            attribute_seq=source_text(record.get("attribute_seq")),
            attribute_korean_name=source_text(record.get("attribute_korean_name")),
            product_yn=source_text(record.get("product_yn")),
            update_reason=source_text(record.get("update_reason")),
            use_yn=source_text(record.get("use_yn")),
            remark=source_text(record.get("remark")),
            food_group_yn=source_text(record.get("food_group_yn")),
            child_favorite_food_yn=source_text(record.get("child_favorite_food_yn")),
            source_updated_at=source_updated_at(record.get("last_updated_at")),
        )


class FoodProductClassificationCreateInternal(FoodProductClassificationBase):
    created_by: str


class FoodProductClassificationReadResponse(FoodProductClassificationBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    version: int


class FoodProductClassificationUpdateRequest(FoodProductClassificationMutable):
    """Every column except the natural key, which is the row's identity."""


class FoodProductClassificationUpdateInternal(FoodProductClassificationUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================


def to_read(node: FoodProductClassification) -> FoodProductClassificationReadResponse:
    return FoodProductClassificationReadResponse.model_validate(node)


def to_read_list(
    nodes: list[FoodProductClassification],
) -> list[FoodProductClassificationReadResponse]:
    return [FoodProductClassificationReadResponse.model_validate(i) for i in nodes]
