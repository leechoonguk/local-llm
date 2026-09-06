# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.nutrition import FoodNutrition
from app.schemas.food.nutrition import (
    FoodNutritionCreateInternal,
    FoodNutritionUpdateInternal,
)


# ============================================================
# Classes
# ============================================================


class FoodNutritionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, food_nutrition_id: UUID) -> FoodNutrition | None:
        return await self.session.get(FoodNutrition, food_nutrition_id)

    async def get_by_natural_key(self, food_code: str) -> FoodNutrition | None:
        """The row the provider's record refers to, by the code it is keyed on.

        The sync has no ids of its own: the only thing an incoming record and a
        stored row share is `food_code`, which is why that column carries
        a unique constraint rather than merely an index. One column, not the
        barcode ledger's pair — I2520 identifies a nutrition by its own code.
        """
        result = await self.session.execute(
            select(FoodNutrition).where(FoodNutrition.food_code == food_code)
        )
        return result.scalar_one_or_none()

    async def list(self, offset: int = 0, limit: int = 100) -> list[FoodNutrition]:
        result = await self.session.execute(select(FoodNutrition).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def create(self, data: FoodNutritionCreateInternal) -> FoodNutrition:
        nutrition = FoodNutrition(**data.model_dump())
        self.session.add(nutrition)
        await self.session.flush()
        return nutrition

    async def update(
        self, food_nutrition_id: UUID, data: FoodNutritionUpdateInternal
    ) -> FoodNutrition | None:
        nutrition = await self.session.get(FoodNutrition, food_nutrition_id)
        if nutrition is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(nutrition, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        nutrition.updated_at = datetime.now(UTC)
        await self.session.flush()
        return nutrition

    async def delete(self, food_nutrition_id: UUID) -> bool:
        nutrition = await self.session.get(FoodNutrition, food_nutrition_id)
        if nutrition is None:
            return False
        await self.session.delete(nutrition)
        return True
