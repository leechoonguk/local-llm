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
from app.models.food.item_report import FoodItemReport
from app.models.food.item_report_ingredient import FoodItemReportIngredient
from app.models.food.raw_material import FoodRawMaterial
from app.schemas.food.item_report import FoodItemReportFilter


# ============================================================
# Constants
# ============================================================


# ============================================================
# Classes
# ============================================================


class FoodItemReportRepository:
    """Reads over the derived report table. Nothing here writes: the derive job does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, food_item_report_id: UUID) -> FoodItemReport | None:
        """One report with its edges loaded - its type (for the standards read), label, nutrition.

        Along the model's own edges (`rule://backend-relations`), loaded in
        three follow-up selects rather than one join: every edge is a list,
        and a single joined row set would multiply the report by the product
        of the three list lengths.
        """
        result = await self.session.execute(
            select(FoodItemReport)
            .where(FoodItemReport.id == food_item_report_id)
            .options(
                selectinload(FoodItemReport.product_classifications),
                selectinload(FoodItemReport.ingredients),
                selectinload(FoodItemReport.nutritions),
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        filters: FoodItemReportFilter | None = None,
        sort: str | None = None,
        order: str = "asc",
    ) -> list[FoodItemReport]:
        narrowed = _apply_filters(select(FoodItemReport), filters)
        query = (
            ordered(
                narrowed,
                FoodItemReport,
                sort,
                order,
                FoodItemReport.report_kind,
                FoodItemReport.item_report_no,
            )
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.execute(query)).scalars().all())

    async def count(self, filters: FoodItemReportFilter | None = None) -> int:
        query = _apply_filters(select(func.count()).select_from(FoodItemReport), filters)
        return (await self.session.execute(query)).scalar_one()

    async def list_by_raw_material(
        self, food_raw_material_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[FoodItemReport]:
        """The reports whose label names this material - along the two edges, as one EXISTS.

        `ingredients.any(material.has(...))` walks report -> ingredient ->
        material on the model's own joins (rule://backend-relations), and an
        EXISTS answers each report once however many times its label repeats
        the name (`당절임, 당절임`). The ingredient's `material_code` index is
        what makes the walk a lookup and not a scan of ten million rows.
        """
        query = (
            _uses_raw_material(select(FoodItemReport), food_raw_material_id)
            .order_by(FoodItemReport.report_kind, FoodItemReport.item_report_no)
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.execute(query)).scalars().all())

    async def count_by_raw_material(self, food_raw_material_id: UUID) -> int:
        query = _uses_raw_material(
            select(func.count()).select_from(FoodItemReport), food_raw_material_id
        )
        return (await self.session.execute(query)).scalar_one()

    async def distinct_values(self, column: str) -> list[str]:
        """Every value one closed-vocabulary column holds, sorted, NULL left out.

        The select filter's options: a value the table does not hold cannot match
        anything, and NULL is the absence of a value, not a choice (measured
        2026-09-10: 4 of 1,640,212 reports carry no 식품유형).

        A parallel scan of the whole table, 431ms measured, not an index walk:
        the column's index answers a value's rows, and Postgres has no loose
        index scan to skip along its distinct keys. That is the cost of a page's
        own `count(*)` on the same table, and this is read once per mount.
        """
        attribute = getattr(FoodItemReport, column)
        query = select(attribute).where(attribute.is_not(None)).distinct().order_by(attribute)
        return list((await self.session.execute(query)).scalars().all())


# ============================================================
# Functions
# ============================================================


def _uses_raw_material(query: Select[Any], food_raw_material_id: UUID) -> Select[Any]:
    """Narrow a report query to the reports whose label names one registry material."""
    return query.where(
        FoodItemReport.ingredients.any(
            FoodItemReportIngredient.material.has(FoodRawMaterial.id == food_raw_material_id)
        )
    )


def _apply_filters(query: Select[Any], filters: FoodItemReportFilter | None) -> Select[Any]:
    """Narrow a report query by each field the caller named.

    One builder for the page and its count, so the two cannot disagree. AND
    across fields - each is its own box on the screen. A registry number, a
    licence, a product or business name match a fragment (`ilike`, wildcards
    added here so a caller never sends SQL); the kind and the 식품유형 match
    whole - the kind is a pair the schema closes, and the type name is picked
    from the column's own values, where a contains-match would only widen it
    (measured 2026-09-10: 77 of the 814 names are a prefix of another, `빵` of `빵류`).
    """
    if filters is None:
        return query
    for column, value in (
        (FoodItemReport.item_report_no, filters.item_report_no),
        (FoodItemReport.license_no, filters.license_no),
        (FoodItemReport.business_name, filters.business_name),
        (FoodItemReport.product_name, filters.product_name),
    ):
        if value is not None:
            query = query.where(column.ilike(f"%{value}%"))
    for column, value in (
        (FoodItemReport.report_kind, filters.report_kind),
        (FoodItemReport.product_type_name, filters.product_type_name),
    ):
        if value is not None:
            query = query.where(column == value)
    return query
