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

AMOUNT_LENGTH = 32

DATE_LENGTH = 20

FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodLedgerQrNutritionMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-qr-nutrition`).
    """

    item_report_serial: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    item_report_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    nutrition_label_serial: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    barcode_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    product_name: MfdsText = None
    business_name: MfdsText = None
    version_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    valid_from: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    valid_to: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    basis_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    total_content_amount: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    total_content_unit: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    unit_content_amount: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    unit_content_unit: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    remark_text: MfdsText = None
    format_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    label_group_name: MfdsText = None
    unit_content_label_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    unit_content_label_amount_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    total_piece_label_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    nutrient_kind_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    nutrient_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    nutrient_sequence: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    amount: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    amount_unit: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    amount_unit_etc: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    daily_value_pct: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_division_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    additional_item_division_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    additional_item_1_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    additional_item_2_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    additional_item_3_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    additional_item_4_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    additional_item_5_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    additional_item_1_amount: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_2_amount: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_3_amount: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_4_amount: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_5_amount: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_1_ratio: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_2_ratio: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_3_ratio: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_4_ratio: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_5_ratio: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_1_unit_etc: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_2_unit_etc: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_3_unit_etc: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_4_unit_etc: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    additional_item_5_unit_etc: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    intake_basis_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    intake_amount: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    intake_amount_unit: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    intake_weight: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    intake_weight_unit: MfdsText = Field(default=None, max_length=AMOUNT_LENGTH)
    source_updated_at: MfdsDatetime = None


class FoodLedgerQrNutritionBase(FoodLedgerQrNutritionMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    label_no: str = Field(max_length=CODE_LENGTH)
    nutrition_detail_serial: str = Field(max_length=CODE_LENGTH)


class FoodLedgerQrNutritionCreateRequest(FoodLedgerQrNutritionBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodLedgerQrNutritionCreateRequest | None:
        """Map one canonical record onto the ledger, or refuse it.

        A record missing either half of its key - the 라벨관리번호 or the
        영양표시상세일련번호 - cannot be matched by a later pass, so it is
        dropped here rather than becoming a row no merge can find again. Every
        other refusal still raises: that is a contract change, not a sparse
        record.
        """
        label_no = cls.key_text(record.get("label_no"))
        if label_no is None:
            return None
        nutrition_detail_serial = cls.key_text(record.get("nutrition_detail_serial"))
        if nutrition_detail_serial is None:
            return None
        return cls.model_validate(
            {
                "label_no": label_no,
                "nutrition_detail_serial": nutrition_detail_serial,
                "item_report_serial": record.get("item_report_serial"),
                "item_report_no": record.get("item_report_no"),
                "nutrition_label_serial": record.get("nutrition_label_serial"),
                "barcode_no": record.get("barcode_no"),
                "product_name": record.get("product_name"),
                "business_name": record.get("business_name"),
                "version_no": record.get("version_no"),
                "valid_from": record.get("valid_from"),
                "valid_to": record.get("valid_to"),
                "basis_name": record.get("basis_name"),
                "total_content_amount": record.get("total_content_amount"),
                "total_content_unit": record.get("total_content_unit"),
                "unit_content_amount": record.get("unit_content_amount"),
                "unit_content_unit": record.get("unit_content_unit"),
                "remark_text": record.get("remark_text"),
                "format_name": record.get("format_name"),
                "label_group_name": record.get("label_group_name"),
                "unit_content_label_name": record.get("unit_content_label_name"),
                "unit_content_label_amount_name": record.get("unit_content_label_amount_name"),
                "total_piece_label_name": record.get("total_piece_label_name"),
                "nutrient_kind_name": record.get("nutrient_kind_name"),
                "nutrient_name": record.get("nutrient_name"),
                "nutrient_sequence": record.get("nutrient_sequence"),
                "amount": record.get("amount"),
                "amount_unit": record.get("amount_unit"),
                "amount_unit_etc": record.get("amount_unit_etc"),
                "daily_value_pct": record.get("daily_value_pct"),
                "additional_item_division_yn": record.get("additional_item_division_yn"),
                "additional_item_division_name": record.get("additional_item_division_name"),
                "additional_item_1_name": record.get("additional_item_1_name"),
                "additional_item_2_name": record.get("additional_item_2_name"),
                "additional_item_3_name": record.get("additional_item_3_name"),
                "additional_item_4_name": record.get("additional_item_4_name"),
                "additional_item_5_name": record.get("additional_item_5_name"),
                "additional_item_1_amount": record.get("additional_item_1_amount"),
                "additional_item_2_amount": record.get("additional_item_2_amount"),
                "additional_item_3_amount": record.get("additional_item_3_amount"),
                "additional_item_4_amount": record.get("additional_item_4_amount"),
                "additional_item_5_amount": record.get("additional_item_5_amount"),
                "additional_item_1_ratio": record.get("additional_item_1_ratio"),
                "additional_item_2_ratio": record.get("additional_item_2_ratio"),
                "additional_item_3_ratio": record.get("additional_item_3_ratio"),
                "additional_item_4_ratio": record.get("additional_item_4_ratio"),
                "additional_item_5_ratio": record.get("additional_item_5_ratio"),
                "additional_item_1_unit_etc": record.get("additional_item_1_unit_etc"),
                "additional_item_2_unit_etc": record.get("additional_item_2_unit_etc"),
                "additional_item_3_unit_etc": record.get("additional_item_3_unit_etc"),
                "additional_item_4_unit_etc": record.get("additional_item_4_unit_etc"),
                "additional_item_5_unit_etc": record.get("additional_item_5_unit_etc"),
                "intake_basis_name": record.get("intake_basis_name"),
                "intake_amount": record.get("intake_amount"),
                "intake_amount_unit": record.get("intake_amount_unit"),
                "intake_weight": record.get("intake_weight"),
                "intake_weight_unit": record.get("intake_weight_unit"),
                "source_updated_at": record.get("source_updated_at"),
            }
        )
