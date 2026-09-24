# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import LedgerStage, scan_table, synced_columns
from app.models.food import test_item as item
from app.models.food.ledger_test_item import FoodLedgerTestItem
from app.models.food.test_item import FoodTestItem


# ============================================================
# Constants
# ============================================================

# The ledger is read in pages of this many rows: 3,393 rows, four pages.
PAGE_SIZE = 1000

# Every column the model declares beyond its key and the audit trail - the
# ledger's own, one for one, so the two cannot drift apart.
SYNCED_COLUMNS = synced_columns(FoodTestItem, item.NATURAL_KEY)


# ============================================================
# Classes
# ============================================================


class FoodTestItemService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def rebuild_test_item(self, synced_by: str) -> int:
        """Write `food_test_item` as a function of the I2570 ledger; return its rows.

        The ledger whole - no filter, no computed column: the derived table
        exists so that its edges can be declared on it and not on the ledger
        (rule://backend-relations). Read off the live ledger in keyed pages,
        staged, and written over in one short transaction (`LedgerStage.replace`,
        no floor: the ledger's own floor already vouched for the rows this reads).
        """
        stage = LedgerStage(self.session, FoodTestItem, item.NATURAL_KEY, SYNCED_COLUMNS)
        async with self.session.begin():
            await stage.create()
        try:
            async with self.session.begin():
                async for page in scan_table(
                    self.session, FoodLedgerTestItem, item.NATURAL_KEY, SYNCED_COLUMNS, PAGE_SIZE
                ):
                    await stage.add(page)
                return await stage.replace(synced_by, floor=None)
        finally:
            async with self.session.begin():
                await stage.drop()
