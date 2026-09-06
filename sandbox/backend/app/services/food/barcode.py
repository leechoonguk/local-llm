# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import AsyncIterable, Mapping, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.ledger import DEFAULT_FLOOR, LedgerStage
from app.models.food.barcode import FoodBarcode
from app.repositories.food.barcode import FoodBarcodeRepository
from app.schemas.food.barcode import (
    FoodBarcodeCreateInternal,
    FoodBarcodeCreateRequest,
    FoodBarcodeUpdateInternal,
    FoodBarcodeUpdateRequest,
)


# ============================================================
# Constants
# ============================================================

# The columns a pass may refresh — read off the update request, which is
# *defined* as the record minus its identity. Listed by hand instead, a column
# added to the ledger would never be staged and the sync would stop refreshing
# it silently; here the list cannot drift from the schema because it is the
# schema.
SYNCED_COLUMNS = tuple(FoodBarcodeUpdateRequest.model_fields)

# What identifies a record across passes: the merge joins the stage to the
# ledger on it, so a row keeps its `id` and `created_at` from one pass to the
# next.
NATURAL_KEY = ("barcode_no", "report_no")


# ============================================================
# Classes
# ============================================================


class FoodBarcodeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.food_barcode_repository = FoodBarcodeRepository(session)

    async def get_barcode(self, food_barcode_id: UUID) -> FoodBarcode:
        barcode = await self.food_barcode_repository.get(food_barcode_id)
        if barcode is None:
            raise NotFoundError(food_barcode_id)
        return barcode

    async def list_barcodes(self, offset: int = 0, limit: int = 100) -> list[FoodBarcode]:
        return await self.food_barcode_repository.list(offset, limit)

    async def create_barcode(self, data: FoodBarcodeCreateRequest, created_by: str) -> FoodBarcode:
        internal = FoodBarcodeCreateInternal(**data.model_dump(), created_by=created_by)
        async with self.session.begin():
            return await self.food_barcode_repository.create(internal)

    async def update_barcode(
        self, food_barcode_id: UUID, data: FoodBarcodeUpdateRequest, updated_by: str
    ) -> FoodBarcode:
        internal = FoodBarcodeUpdateInternal(
            **data.model_dump(exclude_unset=True), updated_by=updated_by
        )
        async with self.session.begin():
            barcode = await self.food_barcode_repository.update(food_barcode_id, internal)
            if barcode is None:
                raise NotFoundError(food_barcode_id)
            return barcode

    async def replace_barcode_ledger(
        self,
        pages: AsyncIterable[Sequence[object]],
        synced_by: str,
        *,
        floor: float = DEFAULT_FLOOR,
    ) -> tuple[int, int]:
        """Replace the ledger with one whole pass of I2570; return (records read, rows changed).

        The pass arrives page by page and each page commits into a stage on
        its own, so the walk — hours long, quota waits included — never holds
        a transaction open; the ledger itself changes in one short merge at
        the end (`LedgerStage`), and a pass that came back under `floor` of
        the live rows is refused there. A record without its natural key is
        skipped where it arrives, and a key the pass sends twice counts once.

        The two numbers answer different questions: `received` is what the
        provider handed over, `written` is what the merge actually changed —
        inserted, updated or deleted — never a row the pass re-sent unchanged.
        """
        stage = LedgerStage(self.session, FoodBarcode, NATURAL_KEY, SYNCED_COLUMNS)
        received = 0
        async with self.session.begin():
            await stage.create()
        try:
            async for page in pages:
                received += len(page)
                parsed = (
                    FoodBarcodeCreateRequest.from_record(record)
                    for record in page
                    if isinstance(record, Mapping)
                )
                rows = [data.model_dump() for data in parsed if data is not None]
                async with self.session.begin():
                    await stage.add(rows)
            async with self.session.begin():
                written = await stage.merge(synced_by, floor=floor)
        finally:
            async with self.session.begin():
                await stage.drop()
        return received, written

    async def delete_barcode(self, food_barcode_id: UUID) -> None:
        async with self.session.begin():
            if not await self.food_barcode_repository.delete(food_barcode_id):
                raise NotFoundError(food_barcode_id)
