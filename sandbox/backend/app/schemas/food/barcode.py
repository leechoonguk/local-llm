# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.mfds_source import source_text, source_updated_at
from app.models.food.barcode import FoodBarcode


# ============================================================
# Constants
# ============================================================

BARCODE_NO_MAX_LENGTH = 32

REPORT_NO_MAX_LENGTH = 50

# Provider free text — the column is String(200) for the same reason.
NAME_MAX_LENGTH = 200

CLASSIFICATION_NAME_MAX_LENGTH = 120


# ============================================================
# Classes
# ============================================================


class FoodBarcodeBase(BaseModel):
    """The ledger's own columns, in the keys the I2570 contract already uses.

    The field names are the operation's canonical response keys
    (`73_seed_barcode_item_info_integration_field`), so a record the client
    returns maps into this model without a translation table — one concept,
    one key, from the wire through the ledger.
    """

    model_config = ConfigDict(extra="forbid")

    barcode_no: str = Field(max_length=BARCODE_NO_MAX_LENGTH)
    report_no: str = Field(max_length=REPORT_NO_MAX_LENGTH)
    report_item_name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    product_name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    company_name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    upper_product_classification_name: str | None = Field(
        default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH
    )
    top_product_classification_name: str | None = Field(
        default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH
    )
    source_updated_at: datetime | None = None


class FoodBarcodeCreateRequest(FoodBarcodeBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodBarcodeCreateRequest | None:
        """Map one canonical I2570 record onto the ledger, or refuse it.

        A record missing either half of the natural key cannot be upserted —
        the next window would insert it a second time — so it is dropped here
        instead of becoming a row no sync can ever match again. Every other
        refusal (a name past its column bound) still raises: that is a
        contract change, not a sparse record.
        """
        barcode_no = source_text(record.get("barcode_no"))
        report_no = source_text(record.get("report_no"))
        if barcode_no is None or report_no is None:
            return None
        return cls(
            barcode_no=barcode_no,
            report_no=report_no,
            report_item_name=source_text(record.get("report_item_name")),
            product_name=source_text(record.get("product_name")),
            company_name=source_text(record.get("company_name")),
            upper_product_classification_name=source_text(
                record.get("upper_product_classification_name")
            ),
            top_product_classification_name=source_text(
                record.get("top_product_classification_name")
            ),
            source_updated_at=source_updated_at(record.get("last_update_datetime")),
        )


class FoodBarcodeCreateInternal(FoodBarcodeBase):
    created_by: str


class FoodBarcodeReadResponse(FoodBarcodeBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class FoodBarcodeUpdateRequest(BaseModel):
    """Every column except the natural key, which is the row's identity.

    Repointing `(barcode_no, report_no)` would silently move a record's
    history onto another item; the sync inserts the new pair instead.
    """

    model_config = ConfigDict(extra="forbid")

    report_item_name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    product_name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    company_name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    upper_product_classification_name: str | None = Field(
        default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH
    )
    top_product_classification_name: str | None = Field(
        default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH
    )
    source_updated_at: datetime | None = None


class FoodBarcodeUpdateInternal(FoodBarcodeUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================


def to_read(barcode: FoodBarcode) -> FoodBarcodeReadResponse:
    return FoodBarcodeReadResponse.model_validate(barcode)


def to_read_list(barcodes: list[FoodBarcode]) -> list[FoodBarcodeReadResponse]:
    return [FoodBarcodeReadResponse.model_validate(i) for i in barcodes]
