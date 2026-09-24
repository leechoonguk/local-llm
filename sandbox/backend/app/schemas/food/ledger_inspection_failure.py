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

# The two telephone columns the portal publishes and never fills: 0 of 572 rows
# carry either (whole feed, 2026-09-14). Declined rather than stored, so the
# ledger has no column that is NULL by contract.
UNSTORED_KEYS = frozenset({"registrar_telephone", "reporter_telephone"})


# ============================================================
# Classes
# ============================================================


class FoodLedgerInspectionFailureMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-inspection-failure`).
    """

    test_result_text: MfdsText = None
    institution_name: MfdsText = None
    item_report_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    license_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    product_name: MfdsText = None
    business_name: MfdsText = None
    address: MfdsText = None
    barcode_no: MfdsText = None
    packaging_unit: MfdsText = None
    manufactured_text: MfdsText = None
    shelf_life_text: MfdsText = None
    product_type_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    registered_on: MfdsText = Field(default=None, max_length=NAME_LENGTH)


class FoodLedgerInspectionFailureBase(FoodLedgerInspectionFailureMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    disposal_seq: str = Field(max_length=CODE_LENGTH)
    test_item_name: str
    standard_text: str


class FoodLedgerInspectionFailureCreateRequest(FoodLedgerInspectionFailureBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodLedgerInspectionFailureCreateRequest | None:
        """Map one canonical record onto the ledger, or refuse it.

        A record missing any part of its key cannot be matched by a later
        pass, so it is dropped here rather than becoming a row no merge can
        find again. Every other refusal still raises: that is a contract
        change, not a sparse record.
        """
        disposal_seq = cls.key_text(record.get("disposal_seq"))
        if disposal_seq is None:
            return None
        test_item_name = cls.key_text(record.get("test_item_name"))
        if test_item_name is None:
            return None
        standard_text = cls.key_text(record.get("standard_text"))
        if standard_text is None:
            return None
        return cls.model_validate(
            {
                "disposal_seq": disposal_seq,
                "test_item_name": test_item_name,
                "standard_text": standard_text,
                "test_result_text": record.get("test_result_text"),
                "institution_name": record.get("institution_name"),
                "item_report_no": record.get("item_report_no"),
                "license_no": record.get("license_no"),
                "product_name": record.get("product_name"),
                "business_name": record.get("business_name"),
                "address": record.get("address"),
                "barcode_no": record.get("barcode_no"),
                "packaging_unit": record.get("packaging_unit"),
                "manufactured_text": record.get("manufactured_text"),
                "shelf_life_text": record.get("shelf_life_text"),
                "product_type_name": record.get("product_type_name"),
                "registered_on": record.get("registered_on"),
            }
        )
