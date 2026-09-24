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

FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodLedgerQrLabelMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-qr-label`).
    """

    food_label_serial: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    product_name: MfdsText = None
    barcode_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    version_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    valid_from: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    valid_to: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    food_division_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    food_type_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    history_tracked_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    irradiated_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    gmo_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    infant_sale_marked_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    high_calorie_low_nutrition_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    pasteurized_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    sterilized_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    refrigerated_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    content_amount_text: MfdsText = None
    shelf_life_text: MfdsText = None
    intake_method_text: MfdsText = None
    functional_info_text: MfdsText = None
    source_updated_at: MfdsDatetime = None


class FoodLedgerQrLabelBase(FoodLedgerQrLabelMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    label_no: str = Field(max_length=CODE_LENGTH)


class FoodLedgerQrLabelCreateRequest(FoodLedgerQrLabelBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodLedgerQrLabelCreateRequest | None:
        """Map one canonical record onto the ledger, or refuse it.

        A record with no `label_no` cannot be matched by a later pass, so it
        is dropped here rather than becoming a row no merge can find again.
        Every other refusal still raises: that is a contract change, not a
        sparse record.
        """
        label_no = cls.key_text(record.get("label_no"))
        if label_no is None:
            return None
        return cls.model_validate(
            {
                "label_no": label_no,
                "food_label_serial": record.get("food_label_serial"),
                "product_name": record.get("product_name"),
                "barcode_no": record.get("barcode_no"),
                "version_no": record.get("version_no"),
                "valid_from": record.get("valid_from"),
                "valid_to": record.get("valid_to"),
                "food_division_name": record.get("food_division_name"),
                "food_type_name": record.get("food_type_name"),
                "history_tracked_yn": record.get("history_tracked_yn"),
                "irradiated_yn": record.get("irradiated_yn"),
                "gmo_yn": record.get("gmo_yn"),
                "infant_sale_marked_yn": record.get("infant_sale_marked_yn"),
                "high_calorie_low_nutrition_yn": record.get("high_calorie_low_nutrition_yn"),
                "pasteurized_yn": record.get("pasteurized_yn"),
                "sterilized_yn": record.get("sterilized_yn"),
                "refrigerated_yn": record.get("refrigerated_yn"),
                "content_amount_text": record.get("content_amount_text"),
                "shelf_life_text": record.get("shelf_life_text"),
                "intake_method_text": record.get("intake_method_text"),
                "functional_info_text": record.get("functional_info_text"),
                "source_updated_at": record.get("source_updated_at"),
            }
        )
