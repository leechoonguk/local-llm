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


# ============================================================
# Classes
# ============================================================


class FoodLedgerCommonStandardExclusionMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-common-standard-exclusion`);
    the identity is three columns here, so the mutable part is only the two
    names and the stamp.
    """

    standard_name: MfdsText = None
    product_name: MfdsText = None
    source_updated_at: MfdsDatetime = None


class FoodLedgerCommonStandardExclusionBase(FoodLedgerCommonStandardExclusionMutable):
    """The mutable columns plus the natural key the ledger matches on - a triple."""

    common_standard_type_code: str = Field(max_length=CODE_LENGTH)
    product_code: str = Field(max_length=CODE_LENGTH)
    test_item_code: str = Field(max_length=CODE_LENGTH)


class FoodLedgerCommonStandardExclusionCreateRequest(FoodLedgerCommonStandardExclusionBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodLedgerCommonStandardExclusionCreateRequest | None:
        """Map one canonical I2610 record onto the ledger, or refuse it.

        A record missing any of the three key columns cannot be upserted -
        the next window would insert it a second time - so it is dropped
        here rather than becoming a row no sync can match again. Every other
        refusal still raises: that is a contract change, not a sparse record.
        """
        common_standard_type_code = cls.key_text(record.get("common_standard_type_code"))
        product_code = cls.key_text(record.get("product_code"))
        test_item_code = cls.key_text(record.get("test_item_code"))
        if common_standard_type_code is None or product_code is None or test_item_code is None:
            return None
        return cls.model_validate(
            {
                "common_standard_type_code": common_standard_type_code,
                "product_code": product_code,
                "test_item_code": test_item_code,
                "standard_name": record.get("standard_name"),
                "product_name": record.get("product_name"),
                "source_updated_at": record.get("last_updated_at"),
            }
        )
