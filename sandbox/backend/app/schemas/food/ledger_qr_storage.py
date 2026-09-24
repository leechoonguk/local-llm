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


class FoodLedgerQrStorageMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-qr-storage`).
    """

    storage_text: MfdsText = None
    product_name: MfdsText = None
    barcode_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    version_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    valid_from: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    valid_to: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    source_updated_at: MfdsDatetime = None


class FoodLedgerQrStorageBase(FoodLedgerQrStorageMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    label_no: str = Field(max_length=CODE_LENGTH)
    detail_serial: str = Field(max_length=CODE_LENGTH)


class FoodLedgerQrStorageCreateRequest(FoodLedgerQrStorageBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodLedgerQrStorageCreateRequest | None:
        """Map one canonical record onto the ledger, or refuse it.

        A record missing any part of its key cannot be matched by a later pass, so
        it is dropped here rather than becoming a row no merge can find again.
        Every other refusal still raises: that is a contract change, not a
        sparse record.
        """
        label_no = cls.key_text(record.get("label_no"))
        if label_no is None:
            return None
        detail_serial = cls.key_text(record.get("detail_serial"))
        if detail_serial is None:
            return None
        return cls.model_validate(
            {
                "label_no": label_no,
                "detail_serial": detail_serial,
                "storage_text": record.get("storage_text"),
                "product_name": record.get("product_name"),
                "barcode_no": record.get("barcode_no"),
                "version_no": record.get("version_no"),
                "valid_from": record.get("valid_from"),
                "valid_to": record.get("valid_to"),
                "source_updated_at": record.get("source_updated_at"),
            }
        )
