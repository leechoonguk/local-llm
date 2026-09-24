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

# Provider free text — the columns are String(200) for the same reason.
NAME_MAX_LENGTH = 200

CLASSIFICATION_NAME_MAX_LENGTH = 120

# `YYYYMMDD` as the portal sends it, with room for the dashed form a sibling
# service of the same portal uses for the same concept.
DATE_TEXT_MAX_LENGTH = 20

USE_FLAG_MAX_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodLedgerRawMaterialMutable(MfdsRecord):
    """Every column a sync may refresh — the record minus its identity.

    Declared once and inherited twice: `FoodLedgerRawMaterialBase` adds the natural
    key to it, `FoodLedgerRawMaterialUpdateRequest` is it. Written out in both places
    instead, the two lists were 24 identical lines that a new column has to be
    added to twice — and the day one of them is missed, the sync stops
    refreshing a column nobody notices until the ledger disagrees with the
    portal.

    The field names are the operation's canonical response keys
    (`search-food-raw-material`), so a record the client returns maps into this
    model without a translation table — one concept, one key, from the wire
    through the ledger.
    """

    representative_raw_material_name: MfdsText = Field(default=None, max_length=NAME_MAX_LENGTH)
    # Unbounded on purpose: these three are synonym *lists* the portal joins
    # into one string (measured over the whole feed, 2026-09-05: 1130/272/311
    # characters), and their columns are `Text`. A bound here would reject a
    # record the ledger can store — and a rejection fails the whole page.
    raw_material_alias: MfdsText = None
    english_name: MfdsText = None
    scientific_name: MfdsText = None
    raw_material_large_class: MfdsText = Field(
        default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH
    )
    raw_material_medium_class: MfdsText = Field(
        default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH
    )
    region_code: MfdsText = Field(default=None, max_length=CODE_MAX_LENGTH)
    region_code_name: MfdsText = Field(default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH)
    process_code: MfdsText = Field(default=None, max_length=CODE_MAX_LENGTH)
    process_code_name: MfdsText = Field(default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH)
    raw_material_status_code: MfdsText = Field(default=None, max_length=CODE_MAX_LENGTH)
    raw_material_status_code_name: MfdsText = Field(
        default=None, max_length=CLASSIFICATION_NAME_MAX_LENGTH
    )
    valid_start_date: MfdsText = Field(default=None, max_length=DATE_TEXT_MAX_LENGTH)
    valid_end_date: MfdsText = Field(default=None, max_length=DATE_TEXT_MAX_LENGTH)
    use_yn: MfdsText = Field(default=None, max_length=USE_FLAG_MAX_LENGTH)
    source_updated_at: MfdsDatetime = None


class FoodLedgerRawMaterialBase(FoodLedgerRawMaterialMutable):
    """The mutable columns plus the one that identifies the row."""

    raw_material_code: str = Field(max_length=CODE_MAX_LENGTH)


class FoodLedgerRawMaterialCreateRequest(FoodLedgerRawMaterialBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodLedgerRawMaterialCreateRequest | None:
        """Map one canonical I2520 record onto the ledger, or refuse it.

        A record with no `raw_material_code` cannot be upserted — the next
        window would insert it a second time — so it is dropped here instead of
        becoming a row no sync can ever match again. Every other refusal (a name
        past its column bound) still raises: that is a contract change, not a
        sparse record.
        """
        raw_material_code = cls.key_text(record.get("raw_material_code"))
        if raw_material_code is None:
            return None
        return cls.model_validate(
            {
                "raw_material_code": raw_material_code,
                "representative_raw_material_name": record.get("representative_raw_material_name"),
                "raw_material_alias": record.get("raw_material_alias"),
                "english_name": record.get("english_name"),
                "scientific_name": record.get("scientific_name"),
                "raw_material_large_class": record.get("raw_material_large_class"),
                "raw_material_medium_class": record.get("raw_material_medium_class"),
                "region_code": record.get("region_code"),
                "region_code_name": record.get("region_code_name"),
                "process_code": record.get("process_code"),
                "process_code_name": record.get("process_code_name"),
                "raw_material_status_code": record.get("raw_material_status_code"),
                "raw_material_status_code_name": record.get("raw_material_status_code_name"),
                "valid_start_date": record.get("valid_start_date"),
                "valid_end_date": record.get("valid_end_date"),
                "use_yn": record.get("use_yn"),
                "source_updated_at": record.get("last_update_datetime"),
            }
        )
