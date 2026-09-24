# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field

from app.schemas.mfds import MfdsKeyText, MfdsRecord, MfdsText


# ============================================================
# Constants
# ============================================================

NAME_LENGTH = 120

DATE_TEXT_LENGTH = 40


# ============================================================
# Classes
# ============================================================


class FoodLedgerImportFoodLabelMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-import-food-label`).
    """

    declaration_kind: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    expiry_from: MfdsText = Field(default=None, max_length=DATE_TEXT_LENGTH)
    expiry_to: MfdsText = Field(default=None, max_length=DATE_TEXT_LENGTH)
    label_text: MfdsText = None
    raw_material_names: MfdsText = None


class FoodLedgerImportFoodLabelBase(FoodLedgerImportFoodLabelMutable):
    """The mutable columns plus the natural key the ledger matches on.

    Every part is `MfdsKeyText`: the key joins the stage to the ledger with `=`,
    and NULL never equals NULL, so a record the publisher left empty in one of
    these columns keeps the empty string as its key value rather than becoming a
    row every pass inserts again.
    """

    importer_name: MfdsKeyText
    product_name: MfdsKeyText
    product_name_en: MfdsKeyText
    product_type_name: MfdsKeyText
    overseas_maker_name: MfdsKeyText
    origin_country: MfdsKeyText = Field(max_length=NAME_LENGTH)
    export_country: MfdsKeyText = Field(max_length=NAME_LENGTH)
    processed_date: MfdsKeyText = Field(max_length=DATE_TEXT_LENGTH)
    expiry_text: MfdsKeyText = Field(max_length=DATE_TEXT_LENGTH)


class FoodLedgerImportFoodLabelCreateRequest(FoodLedgerImportFoodLabelBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodLedgerImportFoodLabelCreateRequest | None:
        """Map one canonical record onto the ledger, or refuse it.

        The publisher states no key, so the record is identified by every column
        it answers except the two texts. A record with no 수입업체 at all is one
        no later pass could match, and is dropped where it is read.
        """
        importer_name = cls.key_text(record.get("importer_name"))
        if importer_name is None:
            return None
        return cls.model_validate(
            {
                "importer_name": importer_name,
                "product_name": record.get("product_name"),
                "product_name_en": record.get("product_name_en"),
                "product_type_name": record.get("product_type_name"),
                "overseas_maker_name": record.get("overseas_maker_name"),
                "origin_country": record.get("origin_country"),
                "export_country": record.get("export_country"),
                "processed_date": record.get("processed_date"),
                "expiry_text": record.get("expiry_text"),
                "declaration_kind": record.get("declaration_kind"),
                "expiry_from": record.get("expiry_from"),
                "expiry_to": record.get("expiry_to"),
                "label_text": record.get("label_text"),
                "raw_material_names": record.get("raw_material_names"),
            }
        )
