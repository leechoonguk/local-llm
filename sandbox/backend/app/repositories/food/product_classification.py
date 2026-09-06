# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.product_classification import FoodProductClassification
from app.schemas.food.product_classification import (
    FoodProductClassificationCreateInternal,
    FoodProductClassificationUpdateInternal,
)


# ============================================================
# Classes
# ============================================================


class FoodProductClassificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, food_product_classification_id: UUID) -> FoodProductClassification | None:
        return await self.session.get(FoodProductClassification, food_product_classification_id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[FoodProductClassification]:
        result = await self.session.execute(
            select(FoodProductClassification).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def create(
        self, data: FoodProductClassificationCreateInternal
    ) -> FoodProductClassification:
        node = FoodProductClassification(**data.model_dump())
        self.session.add(node)
        await self.session.flush()
        return node

    async def update(
        self, food_product_classification_id: UUID, data: FoodProductClassificationUpdateInternal
    ) -> FoodProductClassification | None:
        node = await self.session.get(FoodProductClassification, food_product_classification_id)
        if node is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(node, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        node.updated_at = datetime.now(UTC)
        await self.session.flush()
        return node

    async def delete(self, food_product_classification_id: UUID) -> bool:
        node = await self.session.get(FoodProductClassification, food_product_classification_id)
        if node is None:
            return False
        await self.session.delete(node)
        return True
