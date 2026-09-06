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
from app.models.food.raw_material import FoodRawMaterial
from app.repositories.food.raw_material import FoodRawMaterialRepository
from app.schemas.food.raw_material import (
    FoodRawMaterialCreateInternal,
    FoodRawMaterialCreateRequest,
    FoodRawMaterialFacets,
    FoodRawMaterialFilter,
    FoodRawMaterialUpdateInternal,
    FoodRawMaterialUpdateRequest,
)


# ============================================================
# Constants
# ============================================================

# The columns a stored row and an incoming record are compared on — read off the
# update request, which is *defined* as the record minus its identity. Listed by
# hand instead, a column added to the ledger would keep comparing equal forever
# and the sync would stop refreshing it silently; here the list cannot drift
# from the schema because it is the schema.
SYNCED_COLUMNS = tuple(FoodRawMaterialUpdateRequest.model_fields)


# ============================================================
# Classes
# ============================================================


class FoodRawMaterialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.food_raw_material_repository = FoodRawMaterialRepository(session)

    async def get_raw_material(self, food_raw_material_id: UUID) -> FoodRawMaterial:
        material = await self.food_raw_material_repository.get(food_raw_material_id)
        if material is None:
            raise NotFoundError(food_raw_material_id)
        return material

    async def list_raw_materials(
        self, offset: int = 0, limit: int = 100, filters: FoodRawMaterialFilter | None = None
    ) -> list[FoodRawMaterial]:
        return await self.food_raw_material_repository.list(offset, limit, filters)

    async def count_raw_materials(self, filters: FoodRawMaterialFilter | None = None) -> int:
        """The collection's size under the filters the caller just applied."""
        return await self.food_raw_material_repository.count(filters)

    async def list_raw_material_facets(self) -> FoodRawMaterialFacets:
        """The values the three select filters may offer, from the rows themselves."""
        repository = self.food_raw_material_repository
        return FoodRawMaterialFacets(
            raw_material_large_class=await repository.distinct_values("raw_material_large_class"),
            raw_material_medium_class=await repository.distinct_values("raw_material_medium_class"),
            raw_material_medium_class_by_large=await repository.medium_classes_by_large(),
            raw_material_status_code_name=await repository.distinct_values(
                "raw_material_status_code_name"
            ),
        )

    async def create_raw_material(
        self, data: FoodRawMaterialCreateRequest, created_by: str
    ) -> FoodRawMaterial:
        internal = FoodRawMaterialCreateInternal(**data.model_dump(), created_by=created_by)
        async with self.session.begin():
            return await self.food_raw_material_repository.create(internal)

    async def update_raw_material(
        self, food_raw_material_id: UUID, data: FoodRawMaterialUpdateRequest, updated_by: str
    ) -> FoodRawMaterial:
        internal = FoodRawMaterialUpdateInternal(
            **data.model_dump(exclude_unset=True), updated_by=updated_by
        )
        async with self.session.begin():
            material = await self.food_raw_material_repository.update(
                food_raw_material_id, internal
            )
            if material is None:
                raise NotFoundError(food_raw_material_id)
            return material

    async def update_raw_material_ledger(
        self, payload: dict[str, object] | list[object], synced_by: str
    ) -> tuple[int, int]:
        """Upsert one page of I2520 records; return (records read, rows written).

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
                data = FoodRawMaterialCreateRequest.from_record(record)
                if data is None:
                    continue
                if await self._upsert(data, synced_by):
                    written += 1
        return len(records), written

    async def delete_raw_material(self, food_raw_material_id: UUID) -> None:
        async with self.session.begin():
            if not await self.food_raw_material_repository.delete(food_raw_material_id):
                raise NotFoundError(food_raw_material_id)

    async def _upsert(self, data: FoodRawMaterialCreateRequest, synced_by: str) -> bool:
        """Insert or refresh one record; report whether a row was written.

        Runs inside the caller's transaction — a page is one boundary, and a
        per-record one would leave the window half applied.
        """
        existing = await self.food_raw_material_repository.get_by_natural_key(
            data.raw_material_code
        )
        if existing is None:
            await self.food_raw_material_repository.create(
                FoodRawMaterialCreateInternal(**data.model_dump(), created_by=synced_by)
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
        await self.food_raw_material_repository.update(
            existing.id, FoodRawMaterialUpdateInternal(**changes, updated_by=synced_by)
        )
        return True
