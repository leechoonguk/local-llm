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

#  The columns the portal publishes and leaves empty, or as good as (whole file, 1,545,751 rows,
# 2026-09-23): tong 0.1% filled, ban 0.1% filled, special_address 0% filled, special_dong 2.8%
# filled, special_sub_no 7.1% filled, road_emd_kind 0% filled, road_emd_code 0% filled,
# road_floor_kind 0% filled, road_building_main_no 0% filled, road_building_sub_no 0% filled,
# road_special_address 0% filled. Declined rather than stored, so the ledger has no column that
# is NULL by contract.
UNSTORED_KEYS = frozenset({
    "tong",
    "ban",
    "special_address",
    "special_dong",
    "special_sub_no",
    "road_emd_kind",
    "road_emd_code",
    "road_floor_kind",
    "road_building_main_no",
    "road_building_sub_no",
    "road_special_address",
})  # fmt: skip


# ============================================================
# Classes
# ============================================================


class FoodLedgerBusinessSiteMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-food-business-site`).
    """

    business_name: MfdsText = None
    district: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    is_mountain: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    lot_main_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    lot_sub_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    road_district_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    parcel_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    building_no: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    ufid: MfdsText = Field(default=None, max_length=CODE_LENGTH)


class FoodLedgerBusinessSiteBase(FoodLedgerBusinessSiteMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    license_no: str = Field(max_length=CODE_LENGTH)


class FoodLedgerBusinessSiteCreateRequest(FoodLedgerBusinessSiteBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodLedgerBusinessSiteCreateRequest | None:
        """Map one canonical I2560 record onto the ledger, or refuse it.

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
                "district": record.get("district"),
                "is_mountain": record.get("is_mountain"),
                "lot_main_no": record.get("lot_main_no"),
                "lot_sub_no": record.get("lot_sub_no"),
                "road_district_code": record.get("road_district_code"),
                "parcel_code": record.get("parcel_code"),
                "building_no": record.get("building_no"),
                "ufid": record.get("ufid"),
            }
        )
