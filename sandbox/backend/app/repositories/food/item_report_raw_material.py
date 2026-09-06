# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.item_report_raw_material import FoodItemReportRawMaterial
from app.schemas.food.item_report_raw_material import (
    FoodItemReportRawMaterialCreateInternal,
    FoodItemReportRawMaterialUpdateInternal,
)


# ============================================================
# Classes
# ============================================================


class FoodItemReportRawMaterialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, food_item_report_raw_material_id: UUID) -> FoodItemReportRawMaterial | None:
        return await self.session.get(FoodItemReportRawMaterial, food_item_report_raw_material_id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[FoodItemReportRawMaterial]:
        result = await self.session.execute(
            select(FoodItemReportRawMaterial).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def create(
        self, data: FoodItemReportRawMaterialCreateInternal
    ) -> FoodItemReportRawMaterial:
        report = FoodItemReportRawMaterial(**data.model_dump())
        self.session.add(report)
        await self.session.flush()
        return report

    async def update(
        self, food_item_report_raw_material_id: UUID, data: FoodItemReportRawMaterialUpdateInternal
    ) -> FoodItemReportRawMaterial | None:
        report = await self.session.get(FoodItemReportRawMaterial, food_item_report_raw_material_id)
        if report is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(report, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        report.updated_at = datetime.now(UTC)
        await self.session.flush()
        return report

    async def delete(self, food_item_report_raw_material_id: UUID) -> bool:
        report = await self.session.get(FoodItemReportRawMaterial, food_item_report_raw_material_id)
        if report is None:
            return False
        await self.session.delete(report)
        return True
