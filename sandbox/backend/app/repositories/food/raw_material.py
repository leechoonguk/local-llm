# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.sorting import ordered
from app.models.food.raw_material import FoodRawMaterial
from app.schemas.food.raw_material import FoodRawMaterialFilter


# ============================================================
# Classes
# ============================================================


class FoodRawMaterialRepository:
    """Reads over the derived raw material table. Nothing here writes: the derive job does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, food_raw_material_id: UUID) -> FoodRawMaterial | None:
        """One material with its composition's siblings loaded, along the model's own edge."""
        result = await self.session.execute(
            select(FoodRawMaterial)
            .where(FoodRawMaterial.id == food_raw_material_id)
            .options(selectinload(FoodRawMaterial.variants))
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        filters: FoodRawMaterialFilter | None = None,
        sort: str | None = None,
        order: str = "asc",
    ) -> list[FoodRawMaterial]:
        query = (
            ordered(
                _apply_filters(select(FoodRawMaterial), filters),
                FoodRawMaterial,
                sort,
                order,
                FoodRawMaterial.raw_material_code,
            )
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.execute(query)).scalars().all())

    async def count(self, filters: FoodRawMaterialFilter | None = None) -> int:
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

        The select filter's options: a value the table does not hold cannot
        match anything, and NULL is the absence of a value, not a choice.
        """
        attribute = getattr(FoodRawMaterial, column)
        query = select(attribute).where(attribute.is_not(None)).distinct().order_by(attribute)
        return list((await self.session.execute(query)).scalars().all())


# ============================================================
# Functions
# ============================================================


def _apply_filters(query: Select[Any], filters: FoodRawMaterialFilter | None) -> Select[Any]:
    """Narrow a raw material query by each field the caller named.

    One builder for the page and its count, so the two cannot disagree. AND
    across fields - each is its own box on the screen. Free text matches a
    fragment (`ilike`, wildcards added here so a caller never sends SQL); a
    closed vocabulary matches whole, because its value was picked from the
    column's own list and a contains-match would only widen it (`식물` is a
    prefix of `식물성유지`).
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
        (FoodRawMaterial.use_yn, filters.use_yn),
    ):
        if value is not None:
            query = query.where(column == value)
    return query
