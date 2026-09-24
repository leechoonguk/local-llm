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

LEVEL_LENGTH = 20

FLAG_LENGTH = 20


# ============================================================
# Classes
# ============================================================


class FoodLedgerCommonStandardTypeMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-common-standard-type`).
    """

    standard_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    parent_common_standard_type_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    level: MfdsText = Field(default=None, max_length=LEVEL_LENGTH)
    definition: MfdsText = None
    use_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    source_updated_at: MfdsDatetime = None


class FoodLedgerCommonStandardTypeBase(FoodLedgerCommonStandardTypeMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    common_standard_type_code: str = Field(max_length=CODE_LENGTH)


class FoodLedgerCommonStandardTypeCreateRequest(FoodLedgerCommonStandardTypeBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodLedgerCommonStandardTypeCreateRequest | None:
        """Map one canonical I2590 record onto the ledger, or refuse it.

        A record with no `common_standard_type_code` cannot be upserted - the
        next window would insert it a second time - so it is dropped here
        rather than becoming a row no sync can match again. Every other
        refusal still raises: that is a contract change, not a sparse record.
        """
        common_standard_type_code = cls.key_text(record.get("common_standard_type_code"))
        if common_standard_type_code is None:
            return None
        return cls.model_validate(
            {
                "common_standard_type_code": common_standard_type_code,
                "standard_name": record.get("standard_name"),
                "parent_common_standard_type_code": record.get("parent_common_standard_type_code"),
                "level": record.get("level"),
                "definition": record.get("definition"),
                "use_yn": record.get("use_yn"),
                "source_updated_at": record.get("last_updated_at"),
            }
        )
