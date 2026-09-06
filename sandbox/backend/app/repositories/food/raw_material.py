# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.raw_material import FoodRawMaterial
from app.schemas.food.raw_material import (
    FoodRawMaterialCreateInternal,
    FoodRawMaterialFilter,
    FoodRawMaterialUpdateInternal,
)


# ============================================================
# Classes
# ============================================================


class FoodRawMaterialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, food_raw_material_id: UUID) -> FoodRawMaterial | None:
        return await self.session.get(FoodRawMaterial, food_raw_material_id)

    async def get_by_natural_key(self, raw_material_code: str) -> FoodRawMaterial | None:
        """The row the provider's record refers to, by the code it is keyed on.

        The sync has no ids of its own: the only thing an incoming record and a
        stored row share is `raw_material_code`, which is why that column carries
        a unique constraint rather than merely an index. One column, not the
        barcode ledger's pair — I2520 identifies a material by its own code.
        """
        result = await self.session.execute(
            select(FoodRawMaterial).where(FoodRawMaterial.raw_material_code == raw_material_code)
        )
        return result.scalar_one_or_none()

    async def list(
        self, offset: int = 0, limit: int = 100, filters: FoodRawMaterialFilter | None = None
    ) -> list[FoodRawMaterial]:
        query = _apply_filters(select(FoodRawMaterial), filters).order_by(
            FoodRawMaterial.raw_material_code
        )
        result = await self.session.execute(query.offset(offset).limit(limit))
        return list(result.scalars().all())

    async def count(self, filters: FoodRawMaterialFilter | None = None) -> int:
        """How many rows the unwindowed `list` would return, under the same filters.

        The filters are applied here too, or the footer counts the collection
        while the grid shows a subset of it - "1-3 of 43,609" on three matching rows.
        """
        query = _apply_filters(select(func.count()).select_from(FoodRawMaterial), filters)
        return (await self.session.execute(query)).scalar_one()

    async def medium_classes_by_large(self) -> dict[str, list[str]]:
        """Every (large, medium) pair the rows hold, as the child list per parent.

        Both sorted, both NULL-free, for the same reason `distinct_values` is: a
        select offers what a row can match.
        """
        large, medium = (
            FoodRawMaterial.raw_material_large_class,
            FoodRawMaterial.raw_material_medium_class,
        )
        query = (
            select(large, medium)
            .where(large.is_not(None), medium.is_not(None))
            .distinct()
            .order_by(large, medium)
        )
        grouped: dict[str, list[str]] = {}
        for parent, child in (await self.session.execute(query)).all():
            grouped.setdefault(parent, []).append(child)
        return grouped

    async def distinct_values(self, column: str) -> list[str]:
        """Every value one closed-vocabulary column holds, sorted, NULL left out.

        The select filter's options: a value the ledger does not hold cannot
        match anything, and NULL is the absence of a value, not a choice.
        """
        attribute = getattr(FoodRawMaterial, column)
        query = select(attribute).where(attribute.is_not(None)).distinct().order_by(attribute)
        return list((await self.session.execute(query)).scalars().all())

    async def create(self, data: FoodRawMaterialCreateInternal) -> FoodRawMaterial:
        material = FoodRawMaterial(**data.model_dump())
        self.session.add(material)
        await self.session.flush()
        return material

    async def update(
        self, food_raw_material_id: UUID, data: FoodRawMaterialUpdateInternal
    ) -> FoodRawMaterial | None:
        material = await self.session.get(FoodRawMaterial, food_raw_material_id)
        if material is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(material, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        material.updated_at = datetime.now(UTC)
        await self.session.flush()
        return material

    async def delete(self, food_raw_material_id: UUID) -> bool:
        material = await self.session.get(FoodRawMaterial, food_raw_material_id)
        if material is None:
            return False
        await self.session.delete(material)
        return True


# ============================================================
# Functions
# ============================================================


def _apply_filters(query: Select[Any], filters: FoodRawMaterialFilter | None) -> Select[Any]:
    """Narrow a raw material query by each field the caller named.

    One builder for the page and its count, because two spellings of the same
    predicate is how a filtered list and its total start disagreeing. Combined
    with AND - each is a separate box on the screen.

    Two match kinds, decided by the column: free text is `ilike` with the
    wildcards added here so a caller never sends SQL syntax; a closed vocabulary
    is `==`, because its value was picked from the column's own list and a
    contains-match would widen it (`식물` is a prefix of `식물성유지`).
    """
    if filters is None:
        return query
    for column, value in (
        (FoodRawMaterial.raw_material_code, filters.raw_material_code),
        (
            FoodRawMaterial.representative_raw_material_name,
            filters.representative_raw_material_name,
        ),
        (FoodRawMaterial.raw_material_alias, filters.raw_material_alias),
    ):
        if value is not None:
            query = query.where(column.ilike(f"%{value}%"))
    for column, value in (
        (FoodRawMaterial.raw_material_large_class, filters.raw_material_large_class),
        (FoodRawMaterial.raw_material_medium_class, filters.raw_material_medium_class),
        (FoodRawMaterial.raw_material_status_code_name, filters.raw_material_status_code_name),
    ):
        if value is not None:
            query = query.where(column == value)
    return query
