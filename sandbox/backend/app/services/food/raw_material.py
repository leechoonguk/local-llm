# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import AsyncIterable, Mapping, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.ledger import DEFAULT_FLOOR, LedgerStage
from app.models.food.raw_material import FoodRawMaterial
from app.repositories.food.raw_material import FoodRawMaterialRepository
from app.schemas.food.raw_material import (
    FoodRawMaterialCreateInternal,
    FoodRawMaterialCreateRequest,
    FoodRawMaterialFacets,
    FoodRawMaterialFilter,
    FoodRawMaterialUpdateInternal,
    FoodRawMaterialUpdateRequest,
)


# ============================================================
# Constants
# ============================================================

# The columns a pass may refresh — read off the update request, which is
# *defined* as the record minus its identity. Listed by hand instead, a column
# added to the ledger would never be staged and the sync would stop refreshing
# it silently; here the list cannot drift from the schema because it is the
# schema.
SYNCED_COLUMNS = tuple(FoodRawMaterialUpdateRequest.model_fields)

# What identifies a record across passes: the merge joins the stage to the
# ledger on it, so a row keeps its `id` and `created_at` from one pass to the
# next.
NATURAL_KEY = ("raw_material_code",)


# ============================================================
# Classes
# ============================================================


class FoodRawMaterialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.food_raw_material_repository = FoodRawMaterialRepository(session)

    async def get_raw_material(self, food_raw_material_id: UUID) -> FoodRawMaterial:
        material = await self.food_raw_material_repository.get(food_raw_material_id)
        if material is None:
            raise NotFoundError(food_raw_material_id)
        return material

    async def list_raw_materials(
        self, offset: int = 0, limit: int = 100, filters: FoodRawMaterialFilter | None = None
    ) -> list[FoodRawMaterial]:
        return await self.food_raw_material_repository.list(offset, limit, filters)

    async def count_raw_materials(self, filters: FoodRawMaterialFilter | None = None) -> int:
        """The collection's size under the filters the caller just applied."""
        return await self.food_raw_material_repository.count(filters)

    async def list_raw_material_facets(self) -> FoodRawMaterialFacets:
        """The values the three select filters may offer, from the rows themselves."""
        repository = self.food_raw_material_repository
        return FoodRawMaterialFacets(
            raw_material_large_class=await repository.distinct_values("raw_material_large_class"),
            raw_material_medium_class=await repository.distinct_values("raw_material_medium_class"),
            raw_material_medium_class_by_large=await repository.medium_classes_by_large(),
            raw_material_status_code_name=await repository.distinct_values(
                "raw_material_status_code_name"
            ),
        )

    async def create_raw_material(
        self, data: FoodRawMaterialCreateRequest, created_by: str
    ) -> FoodRawMaterial:
        internal = FoodRawMaterialCreateInternal(**data.model_dump(), created_by=created_by)
        async with self.session.begin():
            return await self.food_raw_material_repository.create(internal)

    async def update_raw_material(
        self, food_raw_material_id: UUID, data: FoodRawMaterialUpdateRequest, updated_by: str
    ) -> FoodRawMaterial:
        internal = FoodRawMaterialUpdateInternal(
            **data.model_dump(exclude_unset=True), updated_by=updated_by
        )
        async with self.session.begin():
            material = await self.food_raw_material_repository.update(
                food_raw_material_id, internal
            )
            if material is None:
                raise NotFoundError(food_raw_material_id)
            return material

    async def replace_raw_material_ledger(
        self,
        pages: AsyncIterable[Sequence[object]],
        synced_by: str,
        *,
        floor: float = DEFAULT_FLOOR,
    ) -> tuple[int, int]:
        """Replace the ledger with one whole pass of I2520; return (records read, rows changed).

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
        stage = LedgerStage(self.session, FoodRawMaterial, NATURAL_KEY, SYNCED_COLUMNS)
        received = 0
        async with self.session.begin():
            await stage.create()
        try:
            async for page in pages:
                received += len(page)
                parsed = (
                    FoodRawMaterialCreateRequest.from_record(record)
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

    async def delete_raw_material(self, food_raw_material_id: UUID) -> None:
        async with self.session.begin():
            if not await self.food_raw_material_repository.delete(food_raw_material_id):
                raise NotFoundError(food_raw_material_id)
