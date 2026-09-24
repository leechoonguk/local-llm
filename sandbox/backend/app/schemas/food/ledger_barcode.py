# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field

from app.schemas.mfds import MfdsRecord, MfdsText


# ============================================================
# Constants
# ============================================================

CODE_LENGTH = 32

NAME_LENGTH = 120

DATE_LENGTH = 20


# ============================================================
# Classes
# ============================================================


class FoodLedgerBarcodeMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot
    be added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-barcode-product-info`).
    """

    permit_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    production_end_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    product_name: MfdsText = None
    shelf_life: MfdsText = None
    product_type_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    business_name: MfdsText = None
    industry_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    site_address: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    closed_business_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)


class FoodLedgerBarcodeBase(FoodLedgerBarcodeMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    barcode_no: str = Field(max_length=CODE_LENGTH)
    item_report_no: str = Field(max_length=CODE_LENGTH)


class FoodLedgerBarcodeCreateRequest(FoodLedgerBarcodeBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodLedgerBarcodeCreateRequest | None:
        """Map one canonical C005 record onto the ledger, or refuse it.

        The key is the pair, so a record missing either half is dropped here
        rather than becoming a row no later pass can match. Every other
        refusal still raises: that is a contract change, not a sparse record.
        """
        barcode_no = cls.key_text(record.get("barcode_no"))
        item_report_no = cls.key_text(record.get("item_report_no"))
        if barcode_no is None or item_report_no is None:
            return None
        return cls.model_validate(
            {
                "barcode_no": barcode_no,
                "item_report_no": item_report_no,
                "permit_date": record.get("permit_date"),
                "production_end_date": record.get("production_end_date"),
                "product_name": record.get("product_name"),
                "shelf_life": record.get("shelf_life"),
                "product_type_name": record.get("product_type_name"),
                "business_name": record.get("business_name"),
                "industry_name": record.get("industry_name"),
                "site_address": record.get("site_address"),
                "closed_business_date": record.get("closed_business_date"),
            }
        )
