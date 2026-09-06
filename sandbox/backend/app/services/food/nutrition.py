# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.food.nutrition import FoodNutrition
from app.repositories.food.nutrition import FoodNutritionRepository
from app.schemas.food.nutrition import (
    FoodNutritionCreateInternal,
    FoodNutritionCreateRequest,
    FoodNutritionUpdateInternal,
    FoodNutritionUpdateRequest,
)


# ============================================================
# Constants
# ============================================================

# The columns a stored row and an incoming record are compared on — read off the
# update request, which is *defined* as the record minus its identity. Listed by
# hand instead, a column added to the ledger would keep comparing equal forever
# and the sync would stop refreshing it silently; here the list cannot drift
# from the schema because it is the schema.
SYNCED_COLUMNS = tuple(FoodNutritionUpdateRequest.model_fields)


# ============================================================
# Classes
# ============================================================


class FoodNutritionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.food_nutrition_repository = FoodNutritionRepository(session)

    async def get_nutrition(self, food_nutrition_id: UUID) -> FoodNutrition:
        material = await self.food_nutrition_repository.get(food_nutrition_id)
        if material is None:
            raise NotFoundError(food_nutrition_id)
        return material

    async def list_nutritions(self, offset: int = 0, limit: int = 100) -> list[FoodNutrition]:
        return await self.food_nutrition_repository.list(offset, limit)

    async def create_nutrition(
        self, data: FoodNutritionCreateRequest, created_by: str
    ) -> FoodNutrition:
        internal = FoodNutritionCreateInternal(**data.model_dump(), created_by=created_by)
        async with self.session.begin():
            return await self.food_nutrition_repository.create(internal)

    async def update_nutrition(
        self, food_nutrition_id: UUID, data: FoodNutritionUpdateRequest, updated_by: str
    ) -> FoodNutrition:
        internal = FoodNutritionUpdateInternal(
            **data.model_dump(exclude_unset=True), updated_by=updated_by
        )
        async with self.session.begin():
            material = await self.food_nutrition_repository.update(food_nutrition_id, internal)
            if material is None:
                raise NotFoundError(food_nutrition_id)
            return material

    async def update_nutrition_ledger(
        self, payload: dict[str, object] | list[object], synced_by: str
    ) -> tuple[int, int]:
        """Upsert one page of I2790 records; return (records read, rows written).

        The two numbers answer different questions and the caller needs both:
        the page's length says whether another window exists, and the written
        count says what actually changed. They differ on every run after the
        first, because a window overlapping the cursor re-sends records the
        ledger already holds — those are matched, compared, and left alone
        rather than rewritten, so `updated_at` and `version` keep meaning "this
        record changed" instead of "the batch ran".

        One transaction per page: a page is the unit the provider hands over,
        so a failure halfway through it leaves no half-imported window.
        """
        records = payload if isinstance(payload, list) else [payload]
        written = 0
        async with self.session.begin():
            for record in records:
                if not isinstance(record, Mapping):
                    continue
                data = FoodNutritionCreateRequest.from_record(record)
                if data is None:
                    continue
                if await self._upsert(data, synced_by):
                    written += 1
        return len(records), written

    async def delete_nutrition(self, food_nutrition_id: UUID) -> None:
        async with self.session.begin():
            if not await self.food_nutrition_repository.delete(food_nutrition_id):
                raise NotFoundError(food_nutrition_id)

    async def _upsert(self, data: FoodNutritionCreateRequest, synced_by: str) -> bool:
        """Insert or refresh one record; report whether a row was written.

        Runs inside the caller's transaction — a page is one boundary, and a
        per-record one would leave the window half applied.
        """
        existing = await self.food_nutrition_repository.get_by_natural_key(data.food_code)
        if existing is None:
            await self.food_nutrition_repository.create(
                FoodNutritionCreateInternal(**data.model_dump(), created_by=synced_by)
            )
            return True
        changes: dict[str, Any] = {}
        for column in SYNCED_COLUMNS:
            stored = getattr(existing, column)
            # SQLite hands `DateTime(timezone=True)` back without its offset, and
            # the column is written in UTC — without this every re-read window
            # would compare unequal and rewrite rows nothing changed about.
            if isinstance(stored, datetime) and stored.tzinfo is None:
                stored = stored.replace(tzinfo=UTC)
            incoming = getattr(data, column)
            if incoming != stored:
                changes[column] = incoming
        if not changes:
            return False
        await self.food_nutrition_repository.update(
            existing.id, FoodNutritionUpdateInternal(**changes, updated_by=synced_by)
        )
        return True
