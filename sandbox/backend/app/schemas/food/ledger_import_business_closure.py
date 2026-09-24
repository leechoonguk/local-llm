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

DATE_LENGTH = 16

NAME_LENGTH = 120

FLAG_LENGTH = 4

#  The columns the portal publishes and leaves empty, or as good as (whole file, 161,045 rows,
# 2026-09-23): president_name 0% filled. Declined rather than stored, so the ledger has no
# column that is NULL by contract.
UNSTORED_KEYS = frozenset({"president_name"})


# ============================================================
# Classes
# ============================================================


class FoodLedgerImportBusinessClosureMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-import-business-closure`).
    """

    business_name: MfdsText = None
    industry_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    permit_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    closed_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    closure_kind: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    district: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    institution_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)


class FoodLedgerImportBusinessClosureBase(FoodLedgerImportBusinessClosureMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    license_no: str = Field(max_length=CODE_LENGTH)


class FoodLedgerImportBusinessClosureCreateRequest(FoodLedgerImportBusinessClosureBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodLedgerImportBusinessClosureCreateRequest | None:
        """Map one canonical I2821 record onto the ledger, or refuse it.

        A record without its 인허가번호 cannot be matched by a later pass, so it
        is dropped here rather than becoming a row no merge can find again (none
        in the file of 2026-09-23 - every row carries one). Every other refusal
        still raises: that is a contract change, not a sparse record.
        """
        license_no = cls.key_text(record.get("license_no"))
        if license_no is None:
            return None
        return cls.model_validate(
            {
                "license_no": license_no,
                "business_name": record.get("business_name"),
                "industry_name": record.get("industry_name"),
                "permit_date": record.get("permit_date"),
                "closed_date": record.get("closed_date"),
                "closure_kind": record.get("closure_kind"),
                "district": record.get("district"),
                "institution_name": record.get("institution_name"),
            }
        )
