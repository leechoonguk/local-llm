# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field

from app.schemas.mfds import MfdsRecord, MfdsText


# ============================================================
# Constants
# ============================================================

CODE_LENGTH = 32

NAME_LENGTH = 120

DATE_LENGTH = 20


# ============================================================
# Classes
# ============================================================


class FoodLedgerHealthFunctionalItemReportMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-health-functional-item-report`).
    """

    product_name: MfdsText = None
    business_name: MfdsText = None
    license_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    permit_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    product_type_name: MfdsText = None
    product_shape: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    product_form: MfdsText = None
    intake_method: MfdsText = None
    primary_functionality: MfdsText = None
    intake_caution: MfdsText = None
    storage_method: MfdsText = None
    standard_spec: MfdsText = None
    shelf_life: MfdsText = None
    packaging_material: MfdsText = None
    packaging_method: MfdsText = None
    functional_indicator: MfdsText = None
    functional_raw_material_names: MfdsText = None
    other_raw_material_names: MfdsText = None
    capsule_raw_material_names: MfdsText = None
    high_calorie_low_nutrition: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    production_ended: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    child_favorite_certified_yn: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    industry_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    source_updated_at: MfdsText = Field(default=None, max_length=DATE_LENGTH)


class FoodLedgerHealthFunctionalItemReportBase(FoodLedgerHealthFunctionalItemReportMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    item_report_no: str = Field(max_length=CODE_LENGTH)


class FoodLedgerHealthFunctionalItemReportCreateRequest(FoodLedgerHealthFunctionalItemReportBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodLedgerHealthFunctionalItemReportCreateRequest | None:
        """Map one canonical record onto the ledger, or refuse it.

        A record missing its 품목제조번호 cannot be matched by a later pass, so it
        is dropped here rather than becoming a row no merge can find again.
        Every other refusal still raises: that is a contract change, not a
        sparse record.
        """
        item_report_no = cls.key_text(record.get("item_report_no"))
        if item_report_no is None:
            return None
        return cls.model_validate(
            {
                "item_report_no": item_report_no,
                "product_name": record.get("product_name"),
                "business_name": record.get("business_name"),
                "license_no": record.get("license_no"),
                "permit_date": record.get("permit_date"),
                "product_type_name": record.get("product_type_name"),
                "product_shape": record.get("product_shape"),
                "product_form": record.get("product_form"),
                "intake_method": record.get("intake_method"),
                "primary_functionality": record.get("primary_functionality"),
                "intake_caution": record.get("intake_caution"),
                "storage_method": record.get("storage_method"),
                "standard_spec": record.get("standard_spec"),
                "shelf_life": record.get("shelf_life"),
                "packaging_material": record.get("packaging_material"),
                "packaging_method": record.get("packaging_method"),
                "functional_indicator": record.get("functional_indicator"),
                "functional_raw_material_names": record.get("functional_raw_material_names"),
                "other_raw_material_names": record.get("other_raw_material_names"),
                "capsule_raw_material_names": record.get("capsule_raw_material_names"),
                "high_calorie_low_nutrition": record.get("high_calorie_low_nutrition"),
                "production_ended": record.get("production_ended"),
                "child_favorite_certified_yn": record.get("child_favorite_certified_yn"),
                "industry_name": record.get("industry_name"),
                "source_updated_at": record.get("source_updated_at"),
            }
        )
