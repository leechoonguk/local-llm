# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.test_item import FoodTestItem
from app.schemas.food.test_item import (
    FoodTestItemCreateInternal,
    FoodTestItemUpdateInternal,
)


# ============================================================
# Classes
# ============================================================


class FoodTestItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, food_test_item_id: UUID) -> FoodTestItem | None:
        return await self.session.get(FoodTestItem, food_test_item_id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[FoodTestItem]:
        result = await self.session.execute(select(FoodTestItem).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def create(self, data: FoodTestItemCreateInternal) -> FoodTestItem:
        item = FoodTestItem(**data.model_dump())
        self.session.add(item)
        await self.session.flush()
        return item

    async def update(
        self, food_test_item_id: UUID, data: FoodTestItemUpdateInternal
    ) -> FoodTestItem | None:
        item = await self.session.get(FoodTestItem, food_test_item_id)
        if item is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        item.updated_at = datetime.now(UTC)
        await self.session.flush()
        return item

    async def delete(self, food_test_item_id: UUID) -> bool:
        item = await self.session.get(FoodTestItem, food_test_item_id)
        if item is None:
            return False
        await self.session.delete(item)
        return True
