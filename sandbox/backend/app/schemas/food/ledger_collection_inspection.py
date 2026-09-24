# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import hashlib
from collections.abc import Mapping

from pydantic import Field

from app.schemas.mfds import MfdsRecord, MfdsText


# ============================================================
# Constants
# ============================================================

DIGEST_LENGTH = 64

CODE_LENGTH = 32

NAME_LENGTH = 120

# The order the digest reads the record in. Fixed here because it is part of the
# key: reorder this tuple and every row in the ledger gets a new id on the next
# pass, which is a rewrite of every reference to it.
DIGEST_COLUMNS = (
    "collection_no",
    "product_name",
    "business_name",
    "address",
    "industry_name",
    "specimen_type",
    "collected_on",
    "judgment",
    "institution_name",
    "item_report_no",
    "plan_title",
    "source_updated_text",
)


# ============================================================
# Classes
# ============================================================


class FoodLedgerCollectionInspectionMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus the digest of itself.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-collection-inspection`).
    """

    collection_no: MfdsText = None
    product_name: MfdsText = None
    business_name: MfdsText = None
    address: MfdsText = None
    industry_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    specimen_type: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    collected_on: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    judgment: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    institution_name: MfdsText = None
    item_report_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    plan_title: MfdsText = None
    source_updated_text: MfdsText = Field(default=None, max_length=NAME_LENGTH)


class FoodLedgerCollectionInspectionBase(FoodLedgerCollectionInspectionMutable):
    """The mutable columns plus the key this record has to be given."""

    record_digest: str = Field(max_length=DIGEST_LENGTH)


class FoodLedgerCollectionInspectionCreateRequest(FoodLedgerCollectionInspectionBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodLedgerCollectionInspectionCreateRequest | None:
        """Map one canonical record onto the ledger, keyed by a digest of itself.

        This feed publishes no identifier - 수거증번호 repeats 651,739 times over
        the whole feed, and so does every composite of the twelve columns - so
        the key is the record. Two rows identical in all twelve values are
        indistinguishable to any reader, and the digest collapses them into one.

        Nothing is refused here: a record with no key cannot occur when the key
        is computed. A record whose *every* column is empty would still digest,
        and it is dropped, because a row that says nothing is not a fact.
        """
        values: dict[str, str | None] = {
            "collection_no": cls.key_text(record.get("collection_no")),
            "product_name": cls.key_text(record.get("product_name")),
            "business_name": cls.key_text(record.get("business_name")),
            "address": cls.key_text(record.get("address")),
            "industry_name": cls.key_text(record.get("industry_name")),
            "specimen_type": cls.key_text(record.get("specimen_type")),
            "collected_on": cls.key_text(record.get("collected_on")),
            "judgment": cls.key_text(record.get("judgment")),
            "institution_name": cls.key_text(record.get("institution_name")),
            "item_report_no": cls.key_text(record.get("item_report_no")),
            "plan_title": cls.key_text(record.get("plan_title")),
            "source_updated_text": cls.key_text(record.get("source_updated_text")),
        }
        if not any(values.values()):
            return None
        joined = "\x1f".join(values[name] or "" for name in DIGEST_COLUMNS)
        return cls.model_validate(
            {
                "record_digest": hashlib.sha256(joined.encode("utf-8")).hexdigest(),
                **values,
            }
        )
