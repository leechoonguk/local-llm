# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.ledger import LedgerStage, scan_table
from app.models.food import raw_material as material
from app.models.food.ledger_raw_material import FoodLedgerRawMaterial
from app.models.food.raw_material import FoodRawMaterial
from app.repositories.food.raw_material import FoodRawMaterialRepository
from app.schemas.food.raw_material import FoodRawMaterialFacets, FoodRawMaterialFilter


# ============================================================
# Constants
# ============================================================

# The ledger is read in pages of this many rows: 43,609 codes, 44 pages.
PAGE_SIZE = 1000

# What the derivation reads off the ledger: its own columns, less the one it
# computes (`base_code`).
LEDGER_COLUMNS = tuple(name for name in material.SYNCED_COLUMNS if name != "base_code")


# ============================================================
# Classes
# ============================================================


class FoodRawMaterialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.raw_material_repository = FoodRawMaterialRepository(session)

    async def get_raw_material(self, food_raw_material_id: UUID) -> FoodRawMaterial:
        raw_material = await self.raw_material_repository.get(food_raw_material_id)
        if raw_material is None:
            raise NotFoundError(food_raw_material_id)
        return raw_material

    async def list_raw_materials(
        self,
        offset: int = 0,
        limit: int = 100,
        filters: FoodRawMaterialFilter | None = None,
        sort: str | None = None,
        order: str = "asc",
    ) -> list[FoodRawMaterial]:
        return await self.raw_material_repository.list(offset, limit, filters, sort, order)

    async def count_raw_materials(self, filters: FoodRawMaterialFilter | None = None) -> int:
        return await self.raw_material_repository.count(filters)

    async def list_raw_material_facets(self) -> FoodRawMaterialFacets:
        """The values the select filters offer: the table's own, read now, not typed once."""
        repository = self.raw_material_repository
        return FoodRawMaterialFacets(
            raw_material_large_class=await repository.distinct_values("raw_material_large_class"),
            raw_material_medium_class=await repository.distinct_values("raw_material_medium_class"),
            raw_material_medium_class_by_large=await repository.medium_classes_by_large(),
            raw_material_status_code_name=await repository.distinct_values(
                "raw_material_status_code_name"
            ),
        )

    async def rebuild_raw_material(self, synced_by: str) -> int:
        """Write `food_raw_material` as a function of the I2520 ledger; return its rows.

        What food is made of: the ledger minus the 기구·용기포장 and 위생용품
        classes (`_is_an_ingredient`, 42,431 of 43,609 measured 2026-09-08),
        each code carrying its composition's base as `base_code` (`_material`).
        Read off the live
        ledger in keyed pages, staged, and written over whole in one short
        transaction (`LedgerStage.replace`, no floor: the ledger's own floor
        already vouched for the rows this reads). Idempotent, so a rule that
        changes is a rebuild and not a walk of the feed.
        """
        stage = LedgerStage(
            self.session, FoodRawMaterial, material.NATURAL_KEY, material.SYNCED_COLUMNS
        )
        async with self.session.begin():
            await stage.create()
        try:
            async with self.session.begin():
                async for page in scan_table(
                    self.session,
                    FoodLedgerRawMaterial,
                    material.NATURAL_KEY,
                    LEDGER_COLUMNS,
                    PAGE_SIZE,
                ):
                    await stage.add([_material(row) for row in page if _is_an_ingredient(row)])
                return await stage.replace(synced_by, floor=None)
        finally:
            async with self.session.begin():
                await stage.drop()


# ============================================================
# Functions
# ============================================================


def _is_an_ingredient(row: Mapping[str, object]) -> bool:
    """Is this a class food is made of, or 기구·용기포장 / 위생용품?"""
    return not str(row["raw_material_code"]).startswith(material.NOT_AN_INGREDIENT)


def _material(row: Mapping[str, object]) -> dict[str, object]:
    """The derived row: the ledger row plus its composition's base, the first eight characters."""
    code = str(row["raw_material_code"])
    return {**row, "base_code": code[: material.BASE_CODE_LENGTH]}
