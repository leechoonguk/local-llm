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


# ============================================================
# Classes
# ============================================================


class FoodLedgerAdminDispositionMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-admin-disposition`).
    """

    license_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    business_name: MfdsText = None
    industry_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    decided_on: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    began_on: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    ended_on: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    disposition_type: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    violation_text: MfdsText = None
    disposition_text: MfdsText = None
    law_text: MfdsText = None
    address: MfdsText = None
    telephone: MfdsText = None
    president_name: MfdsText = None
    institution_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    public_until: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    source_updated_text: MfdsText = Field(default=None, max_length=NAME_LENGTH)


class FoodLedgerAdminDispositionBase(FoodLedgerAdminDispositionMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    disposition_seq: str = Field(max_length=CODE_LENGTH)


class FoodLedgerAdminDispositionCreateRequest(FoodLedgerAdminDispositionBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodLedgerAdminDispositionCreateRequest | None:
        """Map one canonical record onto the ledger, or refuse it.

        A record missing its key cannot be matched by a later pass, so it is
        dropped here rather than becoming a row no merge can find again. Every
        other refusal still raises: that is a contract change, not a sparse
        record.
        """
        disposition_seq = cls.key_text(record.get("disposition_seq"))
        if disposition_seq is None:
            return None
        return cls.model_validate(
            {
                "disposition_seq": disposition_seq,
                "license_no": record.get("license_no"),
                "business_name": record.get("business_name"),
                "industry_name": record.get("industry_name"),
                "decided_on": record.get("decided_on"),
                "began_on": record.get("began_on"),
                "ended_on": record.get("ended_on"),
                "disposition_type": record.get("disposition_type"),
                "violation_text": record.get("violation_text"),
                "disposition_text": record.get("disposition_text"),
                "law_text": record.get("law_text"),
                "address": record.get("address"),
                "telephone": record.get("telephone"),
                "president_name": record.get("president_name"),
                "institution_name": record.get("institution_name"),
                "public_until": record.get("public_until"),
                "source_updated_text": record.get("source_updated_text"),
            }
        )
