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


class FoodLedgerProductClassificationMutable(MfdsRecord):
    """Every column a sync may refresh - the record minus its identity.

    Declared once and inherited twice, so a column added to the ledger cannot be
    added to one list and missed in the other. The field names are the
    operation's canonical response keys (`search-product-classification`).
    """

    level: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    korean_name: MfdsText = None
    english_name: MfdsText = None
    definition: MfdsText = None
    valid_begin_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    valid_end_date: MfdsText = Field(default=None, max_length=DATE_LENGTH)
    parent_product_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    root_product_code: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    mixture_product_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    attribute_seq: MfdsText = Field(default=None, max_length=CODE_LENGTH)
    attribute_korean_name: MfdsText = Field(default=None, max_length=NAME_LENGTH)
    product_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    update_reason: MfdsText = None
    use_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    remark: MfdsText = None
    food_group_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    child_favorite_food_yn: MfdsText = Field(default=None, max_length=FLAG_LENGTH)
    source_updated_at: MfdsDatetime = None


class FoodLedgerProductClassificationBase(FoodLedgerProductClassificationMutable):
    """The mutable columns plus the natural key the ledger matches on."""

    product_code: str = Field(max_length=CODE_LENGTH)


class FoodLedgerProductClassificationCreateRequest(FoodLedgerProductClassificationBase):
    """One provider record, validated before it may become a ledger row."""

    @classmethod
    def from_record(
        cls, record: Mapping[str, object]
    ) -> FoodLedgerProductClassificationCreateRequest | None:
        """Map one canonical I2510 record onto the ledger, or refuse it.

        A record with no `product_code` cannot be matched by a later pass, so
        it is dropped here rather than becoming a row no merge can find again.
        Every other refusal still raises: that is a contract change, not a
        sparse record.
        """
        product_code = cls.key_text(record.get("product_code"))
        if product_code is None:
            return None
        return cls.model_validate(
            {
                "product_code": product_code,
                "level": record.get("level"),
                "korean_name": record.get("korean_name"),
                "english_name": record.get("english_name"),
                "definition": record.get("definition"),
                "valid_begin_date": record.get("valid_begin_date"),
                "valid_end_date": record.get("valid_end_date"),
                "parent_product_code": record.get("parent_product_code"),
                "root_product_code": record.get("root_product_code"),
                "mixture_product_yn": record.get("mixture_product_yn"),
                "attribute_seq": record.get("attribute_seq"),
                "attribute_korean_name": record.get("attribute_korean_name"),
                "product_yn": record.get("product_yn"),
                "update_reason": record.get("update_reason"),
                "use_yn": record.get("use_yn"),
                "remark": record.get("remark"),
                "food_group_yn": record.get("food_group_yn"),
                "child_favorite_food_yn": record.get("child_favorite_food_yn"),
                "source_updated_at": record.get("last_updated_at"),
            }
        )
