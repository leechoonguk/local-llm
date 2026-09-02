# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from app.models.barcode import Barcode


# ============================================================
# Constants
# ============================================================

BARCODE_NO_MAX_LENGTH = 32

REPORT_NO_MAX_LENGTH = 50

# Provider free text — the column is String(200) for the same reason.
NAME_MAX_LENGTH = 200

CLASSIFICATION_NAME_MAX_LENGTH = 120

# The provider is a Korean portal and its 최종수정일시 carries no offset, so the
# reading is KST. Storing it as if it were UTC would move every record nine
# hours and make the sync cursor ask for a window that has already been read.
SOURCE_TIMEZONE = ZoneInfo("Asia/Seoul")

# Measured on I2570: `2024-01-15 09:30:00.0`. The date-only forms are what the
# sibling services of the same portal answer with for the same column, so a
# ledger fed by one of them keeps a usable cursor instead of a null.
SOURCE_DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d")


# ============================================================
# Classes
# ============================================================


class BarcodeBase(BaseModel):
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


class BarcodeCreateRequest(BarcodeBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> BarcodeCreateRequest | None:
        """Map one canonical I2570 record onto the ledger, or refuse it.

        A record missing either half of the natural key cannot be upserted —
        the next window would insert it a second time — so it is dropped here
        instead of becoming a row no sync can ever match again. Every other
        refusal (a name past its column bound) still raises: that is a
        contract change, not a sparse record.
        """
        barcode_no = _text(record.get("barcode_no"))
        report_no = _text(record.get("report_no"))
        if barcode_no is None or report_no is None:
            return None
        return cls(
            barcode_no=barcode_no,
            report_no=report_no,
            report_item_name=_text(record.get("report_item_name")),
            product_name=_text(record.get("product_name")),
            company_name=_text(record.get("company_name")),
            upper_product_classification_name=_text(
                record.get("upper_product_classification_name")
            ),
            top_product_classification_name=_text(record.get("top_product_classification_name")),
            source_updated_at=_source_updated_at(record.get("last_update_datetime")),
        )


class BarcodeCreateInternal(BarcodeBase):
    created_by: str


class BarcodeReadResponse(BarcodeBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class BarcodeUpdateRequest(BaseModel):
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


class BarcodeUpdateInternal(BarcodeUpdateRequest):
    updated_by: str


# ============================================================
# Functions
# ============================================================


def to_read(barcode: Barcode) -> BarcodeReadResponse:
    return BarcodeReadResponse.model_validate(barcode)


def to_read_list(barcodes: list[Barcode]) -> list[BarcodeReadResponse]:
    return [BarcodeReadResponse.model_validate(i) for i in barcodes]


def _text(value: object) -> str | None:
    """A provider string, or None for the empty ones it sends on sparse rows."""
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _source_updated_at(value: object) -> datetime | None:
    """The provider's 최종수정일시 as a UTC timestamp, or None.

    Read as KST (the portal states no offset) and stored as UTC, because a
    database may hand the column back without its offset — SQLite does — and a
    naive value then needs one fixed reading.

    An unreadable stamp keeps the record: the column exists to move the sync
    cursor, and one row written in an unknown shape must not cost the page.
    That row is simply invisible to the high-water mark.
    """
    text = _text(value)
    if text is None:
        return None
    for pattern in SOURCE_DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(text, pattern)
        except ValueError:
            continue
        return parsed.replace(tzinfo=SOURCE_TIMEZONE).astimezone(UTC)
    return None
