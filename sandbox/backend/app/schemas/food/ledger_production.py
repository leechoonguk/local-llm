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

YEAR_LENGTH = 8

NAME_LENGTH = 200

QUANTITY_LENGTH = 32


# ============================================================
# Classes
# ============================================================


class FoodLedgerProductionMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    The field names are the operation's canonical response keys
    (`search-food-production`).
    """

    business_name: MfdsText = None
    product_type_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    production_qty: MfdsText = Field(default=None, max_length=QUANTITY_LENGTH)
    annual_capacity_qty: MfdsText = Field(default=None, max_length=QUANTITY_LENGTH)
    site_address: MfdsText = Field(default=None, max_length=NAME_LENGTH)


class FoodLedgerProductionBase(FoodLedgerProductionMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    item_report_no: str = Field(max_length=CODE_LENGTH)
    report_year: str = Field(max_length=YEAR_LENGTH)
    product_name: str
    license_no: str = Field(max_length=CODE_LENGTH)


class FoodLedgerProductionCreateRequest(FoodLedgerProductionBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodLedgerProductionCreateRequest | None:
        """Map one canonical I0300 record onto the ledger, or refuse it.

        A record missing any part of its four-part key cannot be matched by a
        later pass, so it is dropped here rather than becoming a row no merge
        can find again (5 of 4,000 sampled I0300 rows carry no
        품목제조보고번호, 2026-09-15). Every other refusal still raises: that is
        a contract change, not a sparse record.
        """
        item_report_no = cls.key_text(record.get("item_report_no"))
        report_year = cls.key_text(record.get("report_year"))
        product_name = cls.key_text(record.get("product_name"))
        license_no = cls.key_text(record.get("license_no"))
        if item_report_no is None or report_year is None:
            return None
        if product_name is None or license_no is None:
            return None
        return cls.model_validate(
            {
                "item_report_no": item_report_no,
                "report_year": report_year,
                "product_name": product_name,
                "license_no": license_no,
                "business_name": record.get("business_name"),
                "product_type_name": record.get("product_type_name"),
                "production_qty": record.get("production_qty"),
                "annual_capacity_qty": record.get("annual_capacity_qty"),
                "site_address": record.get("site_address"),
            }
        )
