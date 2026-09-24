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

CODE_MAX_LENGTH = 32

CODE_LENGTH = 32

NAME_LENGTH = 120

FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodLedgerTestItemMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-test-item`).
    """

    korean_name: MfdsText = None
    english_name: MfdsText = None
    abbreviation: MfdsText = None
    alias: MfdsText = None
    test_item_name: MfdsText = None
    major_class_sequence: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    major_class_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    major_class_korean_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    middle_class_sequence: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    middle_class_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    middle_class_korean_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    residue_definition: MfdsText = None
    in_use: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    source_updated_at: MfdsDatetime = None


class FoodLedgerTestItemBase(FoodLedgerTestItemMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    test_item_code: str = Field(max_length=CODE_LENGTH)


class FoodLedgerTestItemCreateRequest(FoodLedgerTestItemBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodLedgerTestItemCreateRequest | None:
        """Map one canonical I2530 record onto the ledger, or refuse it.

        A record with no `test_item_code` cannot be matched by a later pass,
        so it is dropped here rather than becoming a row no merge can find
        again. Every other refusal still raises: that is a contract change,
        not a sparse record.
        """
        test_item_code = cls.key_text(record.get("test_item_code"))
        if test_item_code is None:
            return None
        return cls.model_validate(
            {
                "test_item_code": test_item_code,
                "korean_name": record.get("korean_name"),
                "english_name": record.get("english_name"),
                "abbreviation": record.get("abbreviation"),
                "alias": record.get("alias"),
                "test_item_name": record.get("test_item_name"),
                "major_class_sequence": record.get("major_class_sequence"),
                "major_class_code": record.get("major_class_code"),
                "major_class_korean_name": record.get("major_class_korean_name"),
                "middle_class_sequence": record.get("middle_class_sequence"),
                "middle_class_code": record.get("middle_class_code"),
                "middle_class_korean_name": record.get("middle_class_korean_name"),
                "residue_definition": record.get("residue_definition"),
                "in_use": record.get("in_use"),
                "source_updated_at": record.get("last_updated_at"),
            }
        )
