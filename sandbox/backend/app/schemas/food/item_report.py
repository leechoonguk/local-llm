# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.mfds_source import source_text, source_updated_at
from app.models.food.item_report import FoodItemReport


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


class FoodItemReportMutable(BaseModel):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-item-report`).
    """

    model_config = ConfigDict(extra="forbid")

    license_no: str | None = Field(default=None, max_length=CODE_LENGTH)
    business_name: str | None = None
    permit_date: str | None = Field(default=None, max_length=DATE_LENGTH)
    product_name: str | None = None
    product_type_name: str | None = Field(default=None, max_length=NAME_LENGTH)
    production_ended: str | None = Field(default=None, max_length=NAME_LENGTH)
    high_calorie_low_nutrition: str | None = Field(default=None, max_length=NAME_LENGTH)
    child_favorite_certified_yn: str | None = Field(default=None, max_length=FLAG_LENGTH)
    shelf_life: str | None = None
    industry_name: str | None = Field(default=None, max_length=NAME_LENGTH)
    quality_maintenance_days: str | None = None
    usage_method: str | None = None
    purpose: str | None = None
    product_form: str | None = None
    packaging_material: str | None = None
    domestic_export_type: str | None = Field(default=None, max_length=FLAG_LENGTH)
    source_updated_at: datetime | None = None


class FoodItemReportBase(FoodItemReportMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    item_report_no: str = Field(max_length=CODE_LENGTH)


class FoodItemReportCreateRequest(FoodItemReportBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodItemReportCreateRequest | None:
        """Map one canonical I1250 record onto the ledger, or refuse it.

        A record with no `item_report_no` cannot be upserted - the next window
        would insert it a second time - so it is dropped here rather than
        becoming a row no sync can match again. Every other refusal still
        raises: that is a contract change, not a sparse record.
        """
        item_report_no = source_text(record.get("item_report_no"))
        if item_report_no is None:
            return None
        return cls(
            item_report_no=item_report_no,
            license_no=source_text(record.get("license_no")),
            business_name=source_text(record.get("business_name")),
            permit_date=source_text(record.get("permit_date")),
            product_name=source_text(record.get("product_name")),
            product_type_name=source_text(record.get("product_type_name")),
            production_ended=source_text(record.get("production_ended")),
            high_calorie_low_nutrition=source_text(record.get("high_calorie_low_nutrition")),
            child_favorite_certified_yn=source_text(record.get("child_favorite_certified_yn")),
            shelf_life=source_text(record.get("shelf_life")),
            industry_name=source_text(record.get("industry_name")),
            quality_maintenance_days=source_text(record.get("quality_maintenance_days")),
            usage_method=source_text(record.get("usage_method")),
            purpose=source_text(record.get("purpose")),
            product_form=source_text(record.get("product_form")),
            packaging_material=source_text(record.get("packaging_material")),
            domestic_export_type=source_text(record.get("domestic_export_type")),
            source_updated_at=source_updated_at(record.get("last_updated_date")),
        )


class FoodItemReportCreateInternal(FoodItemReportBase):
    created_by: str


class FoodItemReportReadResponse(FoodItemReportBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    version: int


class FoodItemReportUpdateRequest(FoodItemReportMutable):
    """Every column except the natural key, which is the row's identity."""


class FoodItemReportUpdateInternal(FoodItemReportUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================


def to_read(report: FoodItemReport) -> FoodItemReportReadResponse:
    return FoodItemReportReadResponse.model_validate(report)


def to_read_list(reports: list[FoodItemReport]) -> list[FoodItemReportReadResponse]:
    return [FoodItemReportReadResponse.model_validate(i) for i in reports]
