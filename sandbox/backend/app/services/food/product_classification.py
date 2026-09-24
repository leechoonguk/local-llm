# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import LedgerStage, scan_table
from app.models.food import product_classification as classification
from app.models.food.ledger_product_classification import FoodLedgerProductClassification
from app.models.food.product_classification import FoodProductClassification


# ============================================================
# Constants
# ============================================================

# The ledger is read in pages of this many rows: 9,633 nodes, ten pages.
PAGE_SIZE = 1000

# What the derivation reads off the ledger: its own columns plus the one the
# filter asks and does not keep.
LEDGER_COLUMNS = (*classification.SYNCED_COLUMNS, "valid_end_date")


# ============================================================
# Classes
# ============================================================


class FoodProductClassificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def rebuild_product_classification(self, synced_by: str) -> int:
        """Write `food_product_classification` as a function of the I2510 ledger; return its rows.

        The 공전's tree as it stands: the ledger minus the retired nodes and
        the Z root (`_is_in_the_code`, 6,156 of 9,633 measured 2026-09-08; the
        tiers stay, a 공통기준규격 hangs on them). Read off the live ledger in
        keyed pages, staged, and written over whole in one short transaction
        (`LedgerStage.replace`, no floor: the ledger's own floor already
        vouched for the rows this reads). Idempotent, so a rule that changes
        is a rebuild and not a walk of the feed.
        """
        stage = LedgerStage(
            self.session,
            FoodProductClassification,
            classification.NATURAL_KEY,
            classification.SYNCED_COLUMNS,
        )
        async with self.session.begin():
            await stage.create()
        try:
            async with self.session.begin():
                async for page in scan_table(
                    self.session,
                    FoodLedgerProductClassification,
                    classification.NATURAL_KEY,
                    LEDGER_COLUMNS,
                    PAGE_SIZE,
                ):
                    await stage.add([row for row in page if _is_in_the_code(row)])
                return await stage.replace(synced_by, floor=None)
        finally:
            async with self.session.begin():
                await stage.drop()


# ============================================================
# Functions
# ============================================================


def _is_in_the_code(row: Mapping[str, object]) -> bool:
    """Is this node in the 식품공전 as it stands - not retired, and not under the Z root?"""
    return row["valid_end_date"] == classification.OPEN_ENDED and not str(
        row["product_code"]
    ).startswith(classification.OUT_OF_CODE_ROOT)
