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

DATE_LENGTH = 20


# ============================================================
# Classes
# ============================================================


class FoodLedgerQrAllergyMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-qr-allergy`).
    """

    allergen_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    item_report_serial: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    barcode_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    product_name: MfdsText = None
    label_group_name: MfdsText = None
    version_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    valid_from: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    valid_to: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    source_updated_at: MfdsDatetime = None


class FoodLedgerQrAllergyBase(FoodLedgerQrAllergyMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    label_no: str = Field(max_length=CODE_LENGTH)
    allergen_serial: str = Field(max_length=CODE_LENGTH)


class FoodLedgerQrAllergyCreateRequest(FoodLedgerQrAllergyBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodLedgerQrAllergyCreateRequest | None:
        """Map one canonical record onto the ledger, or refuse it.

        A record missing either half of its key - the 라벨관리번호 or the
        알레르기유발물질일련번호 - cannot be matched by a later pass, so it is
        dropped here rather than becoming a row no merge can find again. Every
        other refusal still raises: that is a contract change, not a sparse
        record.
        """
        label_no = cls.key_text(record.get("label_no"))
        if label_no is None:
            return None
        allergen_serial = cls.key_text(record.get("allergen_serial"))
        if allergen_serial is None:
            return None
        return cls.model_validate(
            {
                "label_no": label_no,
                "allergen_serial": allergen_serial,
                "allergen_name": record.get("allergen_name"),
                "item_report_serial": record.get("item_report_serial"),
                "barcode_no": record.get("barcode_no"),
                "product_name": record.get("product_name"),
                "label_group_name": record.get("label_group_name"),
                "version_no": record.get("version_no"),
                "valid_from": record.get("valid_from"),
                "valid_to": record.get("valid_to"),
                "source_updated_at": record.get("source_updated_at"),
            }
        )
