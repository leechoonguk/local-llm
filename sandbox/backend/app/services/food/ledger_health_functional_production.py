# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import AsyncIterable, Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import DEFAULT_FLOOR, LedgerStage
from app.models.food.ledger_health_functional_production import FoodLedgerHealthFunctionalProduction
from app.schemas.food.ledger_health_functional_production import (
    FoodLedgerHealthFunctionalProductionCreateRequest,
    FoodLedgerHealthFunctionalProductionMutable,
)


# ============================================================
# Constants
# ============================================================

# The columns a pass may refresh - read off the mutable model, which is
# *defined* as the record minus its identity.
SYNCED_COLUMNS = tuple(FoodLedgerHealthFunctionalProductionMutable.model_fields)

# What identifies a record across passes. Four parts, because the 품목제조보고번호
# repeats within one year across product names (measured 2026-09-15).
NATURAL_KEY = ("item_report_no", "report_year", "product_name", "license_no")


# ============================================================
# Classes
# ============================================================


class FoodLedgerHealthFunctionalProductionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_health_functional_production_ledger(
        self,
        pages: AsyncIterable[Sequence[object]],
        synced_by: str,
        *,
        floor: float | None = DEFAULT_FLOOR,
    ) -> tuple[int, int]:
        """Replace the ledger with one whole pass of I0310; return (records read, rows written).

        The pass arrives page by page - here, year by year: the walk asks the
        portal for one 보고년도 at a time and the pages of every year land in
        one stage, which is written over the ledger once at the end
        (`LedgerStage.replace`). That is what keeps this a whole-feed ledger
        while the walk is segmented: the years sum to the feed, so the stage
        holds the feed.

        A pass that came back under `floor` of the live rows is refused there.
        A record without its full natural key is skipped where it arrives, and
        a key the pass sends twice counts once.
        """
        stage = LedgerStage(
            self.session, FoodLedgerHealthFunctionalProduction, NATURAL_KEY, SYNCED_COLUMNS
        )
        received = 0
        async with self.session.begin():
            await stage.create()
        try:
            async for page in pages:
                received += len(page)
                parsed = (
                    FoodLedgerHealthFunctionalProductionCreateRequest.from_record(record)
                    for record in page
                    if isinstance(record, Mapping)
                )
                rows = [data.model_dump() for data in parsed if data is not None]
                async with self.session.begin():
                    await stage.add(rows)
            async with self.session.begin():
                written = await stage.replace(synced_by, floor=floor)
        finally:
            async with self.session.begin():
                await stage.drop()
        return received, written
