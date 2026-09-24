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

DATE_LENGTH = 20

FLAG_LENGTH = 20

VALUE_LENGTH = 120


# ============================================================
# Classes
# ============================================================


class FoodLedgerCommonStandardMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, because 40 fields written out in two
    places is 40 chances to add a column to one list and not the other, and
    the day one is missed the sync stops refreshing it silently. The field
    names are the operation's canonical response keys
    (`search-common-standard`), so a record the client returns maps into
    this model without a translation table.

    The two limit values are strings on purpose: the sibling I2580 writes
    ratios and powers in them (`models/food/common_standard.py`).
    """

    common_standard_type_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    common_standard_type_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    product_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    product_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    test_item_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    detail_item_name: MfdsText = None
    clause_seq: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    clause_name: MfdsText = None
    standard_value: MfdsText = None
    standard_value_summary: MfdsText = None
    valid_begin_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    valid_end_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    source_code: MfdsText = None
    valid_digits: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    judgment_format_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    judgment_format_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    maximum_value: MfdsText = Field(default=None, max_length=VALUE_LENGTH)
    maximum_value_type_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    maximum_value_type_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    minimum_value: MfdsText = Field(default=None, max_length=VALUE_LENGTH)
    minimum_value_type_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    minimum_value_type_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    choice_fit_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    choice_fit_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    choice_unfit_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    choice_unfit_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    microbe_2n: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    microbe_2c: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    microbe_2m: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    microbe_3m: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    detail_item_included_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    hazard_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    priority_inspection_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    monitoring_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    outside_codex_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    self_inspection_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    unit_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    unit_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    update_reason: MfdsText = None
    source_updated_at: MfdsDatetime = None


class FoodLedgerCommonStandardBase(FoodLedgerCommonStandardMutable):
    """The mutable columns plus the two-column natural key the ledger matches on.

    The serial alone repeats (measured 2026-09-07: 16 of 57,440 serials carry
    2-3 rows, one per 시험항목), so the 시험항목 code completes it.
    """

    common_standard_seq: str = Field(max_length=CODE_LENGTH)
    test_item_code: str = Field(max_length=CODE_LENGTH)


class FoodLedgerCommonStandardCreateRequest(FoodLedgerCommonStandardBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodLedgerCommonStandardCreateRequest | None:
        """Map one canonical I2600 record onto the ledger, or refuse it.

        A record with no `common_standard_seq` or no `test_item_code` cannot
        be upserted - the next window would insert it a second time - so it
        is dropped here rather than becoming a row no sync can match again
        (neither was ever empty on the measured feed). Every other refusal
        still raises: that is a contract change, not a sparse record.
        """
        common_standard_seq = cls.key_text(record.get("common_standard_seq"))
        test_item_code = cls.key_text(record.get("test_item_code"))
        if common_standard_seq is None or test_item_code is None:
            return None
        return cls.model_validate(
            {
                "common_standard_seq": common_standard_seq,
                "test_item_code": test_item_code,
                "common_standard_type_code": record.get("common_standard_type_code"),
                "common_standard_type_name": record.get("common_standard_type_name"),
                "product_code": record.get("product_code"),
                "product_name": record.get("product_name"),
                "test_item_name": record.get("test_item_name"),
                "detail_item_name": record.get("detail_item_name"),
                "clause_seq": record.get("clause_seq"),
                "clause_name": record.get("clause_name"),
                "standard_value": record.get("standard_value"),
                "standard_value_summary": record.get("standard_value_summary"),
                "valid_begin_date": record.get("valid_begin_date"),
                "valid_end_date": record.get("valid_end_date"),
                "source_code": record.get("source_code"),
                "valid_digits": record.get("valid_digits"),
                "judgment_format_code": record.get("judgment_format_code"),
                "judgment_format_name": record.get("judgment_format_name"),
                "maximum_value": record.get("maximum_value"),
                "maximum_value_type_code": record.get("maximum_value_type_code"),
                "maximum_value_type_name": record.get("maximum_value_type_name"),
                "minimum_value": record.get("minimum_value"),
                "minimum_value_type_code": record.get("minimum_value_type_code"),
                "minimum_value_type_name": record.get("minimum_value_type_name"),
                "choice_fit_code": record.get("choice_fit_code"),
                "choice_fit_name": record.get("choice_fit_name"),
                "choice_unfit_code": record.get("choice_unfit_code"),
                "choice_unfit_name": record.get("choice_unfit_name"),
                "microbe_2n": record.get("microbe_2n"),
                "microbe_2c": record.get("microbe_2c"),
                "microbe_2m": record.get("microbe_2m"),
                "microbe_3m": record.get("microbe_3m"),
                "detail_item_included_yn": record.get("detail_item_included_yn"),
                "hazard_yn": record.get("hazard_yn"),
                "priority_inspection_yn": record.get("priority_inspection_yn"),
                "monitoring_yn": record.get("monitoring_yn"),
                "outside_codex_yn": record.get("outside_codex_yn"),
                "self_inspection_yn": record.get("self_inspection_yn"),
                "unit_code": record.get("unit_code"),
                "unit_name": record.get("unit_name"),
                "update_reason": record.get("update_reason"),
                "source_updated_at": record.get("last_updated_at"),
            }
        )
