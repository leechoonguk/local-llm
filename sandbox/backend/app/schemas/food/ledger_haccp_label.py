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


class FoodLedgerHaccpLabelMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-haccp-label`).
    """

    product_kind_division: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    product_name: MfdsText = None
    raw_material_names: MfdsText = None
    allergy_names: MfdsText = None
    product_type_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    product_type_state: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    maker_name: MfdsText = None
    seller_name: MfdsText = None
    capacity_text: MfdsText = None


class FoodLedgerHaccpLabelBase(FoodLedgerHaccpLabelMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    item_report_no: str = Field(max_length=CODE_LENGTH)


class FoodLedgerHaccpLabelCreateRequest(FoodLedgerHaccpLabelBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodLedgerHaccpLabelCreateRequest | None:
        """Map one canonical record onto the ledger, or refuse it.

        A record missing any part of its key cannot be matched by a later pass, so
        it is dropped here rather than becoming a row no merge can find again.
        Every other refusal still raises: that is a contract change, not a
        sparse record.
        """
        item_report_no = cls.key_text(record.get("item_report_no"))
        if item_report_no is None:
            return None
        return cls.model_validate(
            {
                "item_report_no": item_report_no,
                "product_kind_division": record.get("product_kind_division"),
                "product_name": record.get("product_name"),
                "raw_material_names": record.get("raw_material_names"),
                "allergy_names": record.get("allergy_names"),
                "product_type_name": record.get("product_type_name"),
                "product_type_state": record.get("product_type_state"),
                "maker_name": record.get("maker_name"),
                "seller_name": record.get("seller_name"),
                "capacity_text": record.get("capacity_text"),
            }
        )
