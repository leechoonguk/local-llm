# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sorting import ordered
from app.models.food.business import FoodBusiness
from app.schemas.food.business import FoodBusinessFilter


# ============================================================
# Classes
# ============================================================


class FoodBusinessRepository:
    """Reads over the derived business table. Nothing here writes: the derive job does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, food_business_id: UUID) -> FoodBusiness | None:
        result = await self.session.execute(
            select(FoodBusiness).where(FoodBusiness.id == food_business_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        filters: FoodBusinessFilter | None = None,
        sort: str | None = None,
        order: str = "asc",
    ) -> list[FoodBusiness]:
        query = (
            ordered(
                _apply_filters(select(FoodBusiness), filters),
                FoodBusiness,
                sort,
                order,
                FoodBusiness.license_no,
            )
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.execute(query)).scalars().all())

    async def count(self, filters: FoodBusinessFilter | None = None) -> int:
        query = _apply_filters(select(func.count()).select_from(FoodBusiness), filters)
        return (await self.session.execute(query)).scalar_one()

    async def list_by_name_key(self, name_key: str, except_id: UUID) -> list[FoodBusiness]:
        """Every other row written under the same name, live first, then by 인허가번호.

        Measured 2026-09-23: 47,795 name keys hold more than one row, 164 at
        the widest (`우리식품`, 100 districts) - a candidate list, never one owner.
        """
        query = (
            select(FoodBusiness)
            .where(FoodBusiness.name_key == name_key, FoodBusiness.id != except_id)
            .order_by(FoodBusiness.status, FoodBusiness.license_no)
        )
        return list((await self.session.execute(query)).scalars().all())

    async def list_by_site_key(self, site_key: str, except_id: UUID) -> list[FoodBusiness]:
        """Every other licence on the same building or parcel.

        Measured 2026-09-23: 2,019 sites hold more than one licence, 95 at the
        widest - a factory licensed for 제조 and 축산가공 at once.
        """
        query = (
            select(FoodBusiness)
            .where(FoodBusiness.site_key == site_key, FoodBusiness.id != except_id)
            .order_by(FoodBusiness.status, FoodBusiness.license_no)
        )
        return list((await self.session.execute(query)).scalars().all())

    async def distinct_values(self, column: str) -> list[str]:
        """Every value one closed-vocabulary column holds, sorted, NULL left out."""
        attribute = getattr(FoodBusiness, column)
        query = select(attribute).where(attribute.is_not(None)).distinct().order_by(attribute)
        return list((await self.session.execute(query)).scalars().all())


# ============================================================
# Functions
# ============================================================


def _apply_filters(query: Select[Any], filters: FoodBusinessFilter | None) -> Select[Any]:
    """Narrow a business query by each field the caller named.

    One builder for the page and its count, so the two cannot disagree. AND
    across fields. Free text (the name, the number, the district) matches a
    fragment; the industry and the status are picked from a closed list and
    matched whole.
    """
    if filters is None:
        return query
    for column, value in (
        (FoodBusiness.business_name, filters.business_name),
        (FoodBusiness.license_no, filters.license_no),
        (FoodBusiness.district, filters.district),
    ):
        if value is not None:
            query = query.where(column.ilike(f"%{value}%"))
    for column, value in (
        (FoodBusiness.industry_name, filters.industry_name),
        (FoodBusiness.status, filters.status),
    ):
        if value is not None:
            query = query.where(column == value)
    return query
