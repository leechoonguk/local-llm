# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import AsyncIterable, Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import DEFAULT_FLOOR, LedgerStage
from app.models.food.ledger_individual_standard import FoodLedgerIndividualStandard
from app.schemas.food.ledger_individual_standard import (
    FoodLedgerIndividualStandardCreateRequest,
    FoodLedgerIndividualStandardMutable,
)


# ============================================================
# Constants
# ============================================================

# The columns a pass may refresh — read off the mutable model, which is
# *defined* as the record minus its identity. Listed by hand instead, a column
# added to the ledger would never be staged and the sync would stop refreshing
# it silently; here the list cannot drift from the schema because it is the
# schema.
SYNCED_COLUMNS = tuple(FoodLedgerIndividualStandardMutable.model_fields)

# What identifies a record across passes: the stage dedupes on it and mints
# the row's `id` from it, so a row keeps its `id` from one pass to the next.
# Not the documented serial alone: measured 2026-09-07 over the whole
# feed (16,401 rows), 322 serials repeat - across 시험항목, across 세부항목
# (a sum rule beside its component) and across 단서조항 (a 살균 clause beside
# a 멸균 one) - and only the four together are unique (revision 133).
NATURAL_KEY = ("individual_standard_seq", "test_item_code", "detail_item_name", "clause_seq")


# ============================================================
# Classes
# ============================================================


class FoodLedgerIndividualStandardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_individual_standard_ledger(
        self,
        pages: AsyncIterable[Sequence[object]],
        synced_by: str,
        *,
        floor: float = DEFAULT_FLOOR,
    ) -> tuple[int, int]:
        """Replace the ledger with one whole pass of I2580; return (records read, rows written).

        The pass arrives page by page and each page commits into a stage on
        its own, so the walk never holds a transaction open; the ledger itself
        is written over in one short transaction at the end
        (`LedgerStage.replace`), and a pass that came back under `floor` of
        the live rows is refused there. A record
        without its natural key is skipped where it arrives, and a key the
        pass sends twice counts once - the first reading stands (the stage
        rule every sibling ledger has; the measured feed never repeats the
        four-column key, only the serial).

        The two numbers answer different questions: `received` is what the
        provider handed over, `written` is what the ledger holds afterwards —
        the pass minus the skipped and the repeated.
        """
        stage = LedgerStage(self.session, FoodLedgerIndividualStandard, NATURAL_KEY, SYNCED_COLUMNS)
        received = 0
        async with self.session.begin():
            await stage.create()
        try:
            async for page in pages:
                received += len(page)
                parsed = (
                    FoodLedgerIndividualStandardCreateRequest.from_record(record)
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
