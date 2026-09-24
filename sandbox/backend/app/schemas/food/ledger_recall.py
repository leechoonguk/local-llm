# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field

from app.schemas.mfds import MfdsDatetime, MfdsRecord, MfdsText


# ============================================================
# Constants
# ============================================================

CODE_LENGTH = 32

NAME_LENGTH = 120


# ============================================================
# Classes
# ============================================================


class FoodLedgerRecallMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-recall`).
    """

    item_report_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    license_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    product_name: MfdsText = None
    business_name: MfdsText = None
    address: MfdsText = None
    telephone: MfdsText = None
    barcode_no: MfdsText = None
    packaging_unit: MfdsText = None
    manufactured_text: MfdsText = None
    recall_reason: MfdsText = None
    recall_method: MfdsText = None
    recall_grade: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    shelf_life_text: MfdsText = None
    product_type_group: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    product_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    product_type_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    image_url: MfdsText = None
    registered_at: MfdsDatetime = None


class FoodLedgerRecallBase(FoodLedgerRecallMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    recall_disuse_seq: str = Field(max_length=CODE_LENGTH)


class FoodLedgerRecallCreateRequest(FoodLedgerRecallBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodLedgerRecallCreateRequest | None:
        """Map one canonical record onto the ledger, or refuse it.

        A record missing any part of its key cannot be matched by a later pass,
        so it is dropped here rather than becoming a row no merge can find
        again. Every other refusal still raises: that is a contract change, not
        a sparse record.
        """
        recall_disuse_seq = cls.key_text(record.get("recall_disuse_seq"))
        if recall_disuse_seq is None:
            return None
        return cls.model_validate(
            {
                "recall_disuse_seq": recall_disuse_seq,
                "item_report_no": record.get("item_report_no"),
                "license_no": record.get("license_no"),
                "product_name": record.get("product_name"),
                "business_name": record.get("business_name"),
                "address": record.get("address"),
                "telephone": record.get("telephone"),
                "barcode_no": record.get("barcode_no"),
                "packaging_unit": record.get("packaging_unit"),
                "manufactured_text": record.get("manufactured_text"),
                "recall_reason": record.get("recall_reason"),
                "recall_method": record.get("recall_method"),
                "recall_grade": record.get("recall_grade"),
                "shelf_life_text": record.get("shelf_life_text"),
                "product_type_group": record.get("product_type_group"),
                "product_code": record.get("product_code"),
                "product_type_name": record.get("product_type_name"),
                "image_url": record.get("image_url"),
                "registered_at": record.get("registered_at"),
            }
        )
