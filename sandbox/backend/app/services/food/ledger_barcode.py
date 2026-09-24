# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import AsyncIterable, Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import DEFAULT_FLOOR, LedgerStage
from app.models.food.ledger_barcode import FoodLedgerBarcode
from app.schemas.food.ledger_barcode import (
    FoodLedgerBarcodeCreateRequest,
    FoodLedgerBarcodeMutable,
)


# ============================================================
# Constants
# ============================================================

# The columns a pass may refresh — read off the mutable model, which is
# *defined* as the record minus its identity. Listed by hand instead, a column
# added to the ledger would never be staged and the sync would stop refreshing
# it silently; here the list cannot drift from the schema because it is the
# schema.
SYNCED_COLUMNS = tuple(FoodLedgerBarcodeMutable.model_fields)

# What identifies a record across passes: the pair, because 229,040 barcodes
# and 149,006 품목보고번호 make neither half unique on its own (whole feed,
# 2026-09-12). The stage dedupes on it and mints the row's `id` from it.
NATURAL_KEY = ("barcode_no", "item_report_no")


# ============================================================
# Classes
# ============================================================


class FoodLedgerBarcodeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_barcode_ledger(
        self,
        pages: AsyncIterable[Sequence[object]],
        synced_by: str,
        *,
        floor: float = DEFAULT_FLOOR,
    ) -> tuple[int, int]:
        """Replace the ledger with one whole pass of C005; return (records read, rows written).

        The pass arrives page by page and each page commits into a stage on
        its own; the ledger itself is written over in one short transaction at
        the end (`LedgerStage.replace`), and a pass that came back under
        `floor` of the live rows is refused there. A record missing either
        half of the pair is skipped where it arrives, and a pair the pass
        sends twice counts once — 13,474 of the feed's 259,669 records do
        (2026-09-12), so `written` is the smaller number by construction.

        The two numbers answer different questions: `received` is what the
        provider handed over, `written` is what the ledger holds afterwards —
        the pass minus the skipped and the repeated.
        """
        stage = LedgerStage(self.session, FoodLedgerBarcode, NATURAL_KEY, SYNCED_COLUMNS)
        received = 0
        async with self.session.begin():
            await stage.create()
        try:
            async for page in pages:
                received += len(page)
                parsed = (
                    FoodLedgerBarcodeCreateRequest.from_record(record)
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
