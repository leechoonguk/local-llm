# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import AsyncIterable, Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import DEFAULT_FLOOR, LedgerStage
from app.models.food.ledger_qr_raw_material import FoodLedgerQrRawMaterial
from app.schemas.food.ledger_qr_raw_material import (
    FoodLedgerQrRawMaterialCreateRequest,
    FoodLedgerQrRawMaterialMutable,
)


# ============================================================
# Constants
# ============================================================

# The columns a pass may refresh — read off the mutable model, which is
# *defined* as the record minus its identity. Listed by hand instead, a column
# added to the ledger would never be staged and the sync would stop refreshing
# it silently; here the list cannot drift from the schema because it is the
# schema.
SYNCED_COLUMNS = tuple(FoodLedgerQrRawMaterialMutable.model_fields)

# What identifies a record across passes: the stage dedupes on it and mints
# the row's `id` from it, so a row keeps its `id` from one pass to the next.
NATURAL_KEY = ("label_no", "raw_material_serial")


# ============================================================
# Classes
# ============================================================


class FoodLedgerQrRawMaterialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_qr_raw_material_ledger(
        self,
        pages: AsyncIterable[Sequence[object]],
        synced_by: str,
        *,
        floor: float = DEFAULT_FLOOR,
    ) -> tuple[int, int]:
        """Replace the ledger with one whole pass; return (records read, rows written).

        The pass arrives page by page and each page commits into a stage on
        its own, as every ledger does. The ledger itself is written over in one
        short transaction at the end (`LedgerStage.replace`), and a pass that
        came back under `floor` of the live rows is refused there. A record
        without its natural key is skipped where it arrives, and a key the pass
        sends twice counts once.

        The two numbers answer different questions: `received` is what the
        provider handed over, `written` is what the ledger holds afterwards —
        the pass minus the skipped and the repeated.
        """
        stage = LedgerStage(self.session, FoodLedgerQrRawMaterial, NATURAL_KEY, SYNCED_COLUMNS)
        received = 0
        async with self.session.begin():
            await stage.create()
        try:
            async for page in pages:
                received += len(page)
                parsed = (
                    FoodLedgerQrRawMaterialCreateRequest.from_record(record)
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
