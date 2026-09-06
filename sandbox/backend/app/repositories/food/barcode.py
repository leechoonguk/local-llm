# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.barcode import FoodBarcode
from app.schemas.food.barcode import FoodBarcodeCreateInternal, FoodBarcodeUpdateInternal


# ============================================================
# Classes
# ============================================================


class FoodBarcodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, food_barcode_id: UUID) -> FoodBarcode | None:
        return await self.session.get(FoodBarcode, food_barcode_id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[FoodBarcode]:
        result = await self.session.execute(select(FoodBarcode).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def create(self, data: FoodBarcodeCreateInternal) -> FoodBarcode:
        barcode = FoodBarcode(**data.model_dump())
        self.session.add(barcode)
        await self.session.flush()
        return barcode

    async def update(
        self, food_barcode_id: UUID, data: FoodBarcodeUpdateInternal
    ) -> FoodBarcode | None:
        barcode = await self.session.get(FoodBarcode, food_barcode_id)
        if barcode is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(barcode, field, value)
        # Set before the flush: the column's onupdate=func.now() is a SQL function
        # whose lazy evaluation raises MissingGreenlet, and a post-flush assignment
        # would cost a second UPDATE (and a second version bump).
        barcode.updated_at = datetime.now(UTC)
        await self.session.flush()
        return barcode

    async def delete(self, food_barcode_id: UUID) -> bool:
        barcode = await self.session.get(FoodBarcode, food_barcode_id)
        if barcode is None:
            return False
        await self.session.delete(barcode)
        return True
