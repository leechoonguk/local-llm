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

FLAG_LENGTH = 4


# ============================================================
# Classes
# ============================================================


class FoodLedgerItemReportMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-item-report`).
    """

    license_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    business_name: MfdsText = None
    permit_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    product_name: MfdsText = None
    product_type_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    production_ended: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    high_calorie_low_nutrition: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    child_favorite_certified_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    shelf_life: MfdsText = None
    industry_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    quality_maintenance_days: MfdsText = None
    usage_method: MfdsText = None
    purpose: MfdsText = None
    product_form: MfdsText = None
    packaging_material: MfdsText = None
    domestic_export_type: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    source_updated_at: MfdsDatetime = None


class FoodLedgerItemReportBase(FoodLedgerItemReportMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    item_report_no: str = Field(max_length=CODE_LENGTH)


class FoodLedgerItemReportCreateRequest(FoodLedgerItemReportBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> FoodLedgerItemReportCreateRequest | None:
        """Map one canonical I1250 record onto the ledger, or refuse it.

        A record with no `item_report_no` cannot be upserted - the next window
        would insert it a second time - so it is dropped here rather than
        becoming a row no sync can match again. Every other refusal still
        raises: that is a contract change, not a sparse record.
        """
        item_report_no = cls.key_text(record.get("item_report_no"))
        if item_report_no is None:
            return None
        return cls.model_validate(
            {
                "item_report_no": item_report_no,
                "license_no": record.get("license_no"),
                "business_name": record.get("business_name"),
                "permit_date": record.get("permit_date"),
                "product_name": record.get("product_name"),
                "product_type_name": record.get("product_type_name"),
                "production_ended": record.get("production_ended"),
                "high_calorie_low_nutrition": record.get("high_calorie_low_nutrition"),
                "child_favorite_certified_yn": record.get("child_favorite_certified_yn"),
                "shelf_life": record.get("shelf_life"),
                "industry_name": record.get("industry_name"),
                "quality_maintenance_days": record.get("quality_maintenance_days"),
                "usage_method": record.get("usage_method"),
                "purpose": record.get("purpose"),
                "product_form": record.get("product_form"),
                "packaging_material": record.get("packaging_material"),
                "domestic_export_type": record.get("domestic_export_type"),
                "source_updated_at": record.get("last_updated_date"),
            }
        )
