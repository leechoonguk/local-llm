# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import AsyncIterable, Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import DEFAULT_FLOOR, LedgerStage
from app.models.food.ledger_import_business_closure import (
    FoodLedgerImportBusinessClosure,
)
from app.schemas.food.ledger_import_business_closure import (
    FoodLedgerImportBusinessClosureCreateRequest,
    FoodLedgerImportBusinessClosureMutable,
)


# ============================================================
# Constants
# ============================================================

# The columns a pass may refresh - read off the mutable model, which is
# *defined* as the record minus its identity.
SYNCED_COLUMNS = tuple(FoodLedgerImportBusinessClosureMutable.model_fields)

# What identifies a record across passes: the 인허가번호, one per row.
NATURAL_KEY = ("license_no",)


# ============================================================
# Classes
# ============================================================


class FoodLedgerImportBusinessClosureService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_import_business_closure_ledger(
        self,
        pages: AsyncIterable[Sequence[object]],
        synced_by: str,
        *,
        floor: float | None = DEFAULT_FLOOR,
    ) -> tuple[int, int]:
        """Replace the ledger with one whole pass of I2821; return (read, written).

        The pass arrives page by page - here, chunk by chunk of one file - and
        lands in one stage, which is written over the ledger once at the end
        (`LedgerStage.replace`). A pass that came back under `floor` of the live rows is refused
        there. A record without its key is skipped where it arrives, and a key the file carries
        twice counts once - the first reading.
        """
        stage = LedgerStage(
            self.session, FoodLedgerImportBusinessClosure, NATURAL_KEY, SYNCED_COLUMNS
        )
        received = 0
        async with self.session.begin():
            await stage.create()
        try:
            async for page in pages:
                received += len(page)
                parsed = (
                    FoodLedgerImportBusinessClosureCreateRequest.from_record(record)
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
