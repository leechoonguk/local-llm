# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import LedgerStage, scan_table, synced_columns
from app.models.food import common_standard_type as standard_type
from app.models.food.common_standard_type import FoodCommonStandardType
from app.models.food.ledger_common_standard_type import FoodLedgerCommonStandardType


# ============================================================
# Constants
# ============================================================

# The ledger is read in pages of this many rows: 90 rows, one page.
PAGE_SIZE = 1000

# Every column the model declares beyond its key and the audit trail - the
# ledger's own, one for one, so the two cannot drift apart.
SYNCED_COLUMNS = synced_columns(FoodCommonStandardType, standard_type.NATURAL_KEY)


# ============================================================
# Classes
# ============================================================


class FoodCommonStandardTypeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def rebuild_common_standard_type(self, synced_by: str) -> int:
        """Write `food_common_standard_type` as a function of the I2590 ledger; return its rows.

        The ledger whole - no filter, no computed column: the derived table
        exists so that its edges can be declared on it and not on the ledger
        (rule://backend-relations). Read off the live ledger in keyed pages,
        staged, and written over in one short transaction (`LedgerStage.replace`,
        no floor: the ledger's own floor already vouched for the rows this reads).
        """
        stage = LedgerStage(
            self.session, FoodCommonStandardType, standard_type.NATURAL_KEY, SYNCED_COLUMNS
        )
        async with self.session.begin():
            await stage.create()
        try:
            async with self.session.begin():
                async for page in scan_table(
                    self.session,
                    FoodLedgerCommonStandardType,
                    standard_type.NATURAL_KEY,
                    SYNCED_COLUMNS,
                    PAGE_SIZE,
                ):
                    await stage.add(page)
                return await stage.replace(synced_by, floor=None)
        finally:
            async with self.session.begin():
                await stage.drop()
