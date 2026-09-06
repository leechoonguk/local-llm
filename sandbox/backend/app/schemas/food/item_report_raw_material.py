# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.mfds_source import source_text, source_updated_at
from app.models.food.item_report_raw_material import FoodItemReportRawMaterial


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


class FoodItemReportRawMaterialMutable(BaseModel):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-item-report-raw-material`);
    the two comma-joined lists arrive and are stored as the portal joins them.
    """

    model_config = ConfigDict(extra="forbid")

    license_no: str | None = Field(default=None, max_length=CODE_LENGTH)
    business_name: str | None = None
    permit_date: str | None = Field(default=None, max_length=DATE_LENGTH)
    product_name: str | None = None
    product_type_name: str | None = Field(default=None, max_length=NAME_LENGTH)
    raw_material_names: str | None = None
    raw_material_ordinals: str | None = None
    domestic_export_type: str | None = Field(default=None, max_length=FLAG_LENGTH)
    source_updated_at: datetime | None = None


class FoodItemReportRawMaterialBase(FoodItemReportRawMaterialMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    item_report_no: str = Field(max_length=CODE_LENGTH)


class FoodItemReportRawMaterialCreateRequest(FoodItemReportRawMaterialBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodItemReportRawMaterialCreateRequest | None:
        """Map one canonical C002 record onto the ledger, or refuse it.

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
            raw_material_names=source_text(record.get("raw_material_names")),
            raw_material_ordinals=source_text(record.get("raw_material_ordinals")),
            domestic_export_type=source_text(record.get("domestic_export_type")),
            source_updated_at=source_updated_at(record.get("changed_date")),
        )


class FoodItemReportRawMaterialCreateInternal(FoodItemReportRawMaterialBase):
    created_by: str


class FoodItemReportRawMaterialReadResponse(FoodItemReportRawMaterialBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    version: int


class FoodItemReportRawMaterialUpdateRequest(FoodItemReportRawMaterialMutable):
    """Every column except the natural key, which is the row's identity."""


class FoodItemReportRawMaterialUpdateInternal(FoodItemReportRawMaterialUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================


def to_read(report: FoodItemReportRawMaterial) -> FoodItemReportRawMaterialReadResponse:
    return FoodItemReportRawMaterialReadResponse.model_validate(report)


def to_read_list(
    reports: list[FoodItemReportRawMaterial],
) -> list[FoodItemReportRawMaterialReadResponse]:
    return [FoodItemReportRawMaterialReadResponse.model_validate(i) for i in reports]
