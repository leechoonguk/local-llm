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


class FoodLedgerItemReportRawMaterialMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-item-report-raw-material`);
    the two comma-joined lists arrive and are stored as the portal joins them.
    """

    license_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    business_name: MfdsText = None
    permit_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    product_name: MfdsText = None
    product_type_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    raw_material_names: MfdsText = None
    raw_material_ordinals: MfdsText = None
    domestic_export_type: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    source_updated_at: MfdsDatetime = None


class FoodLedgerItemReportRawMaterialBase(FoodLedgerItemReportRawMaterialMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    item_report_no: str = Field(max_length=CODE_LENGTH)


class FoodLedgerItemReportRawMaterialCreateRequest(FoodLedgerItemReportRawMaterialBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodLedgerItemReportRawMaterialCreateRequest | None:
        """Map one canonical C002 record onto the ledger, or refuse it.

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
                "raw_material_names": record.get("raw_material_names"),
                "raw_material_ordinals": record.get("raw_material_ordinals"),
                "domestic_export_type": record.get("domestic_export_type"),
                "source_updated_at": record.get("changed_date"),
            }
        )
