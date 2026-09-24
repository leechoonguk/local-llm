# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.label_packaging import FoodLabelPackaging


# ============================================================
# Classes
# ============================================================


class FoodLabelPackagingRepository:
    """Reads over the derived 포장재질 rows. Nothing here writes: the derive job does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_labels(
        self, labels: Sequence[tuple[str, str]]
    ) -> Sequence[FoodLabelPackaging]:
        """Every packaging part of the labels asked for, in printed order.

        Only 푸드QR publishes the parts (6,914 rows over 3,809 라벨, measured
        2026-09-13); the report's own one-string `packaging_material` is what a
        label-less product shows."""
        if not labels:
            return []
        rows = await self.session.execute(
            select(FoodLabelPackaging)
            .where(
                tuple_(FoodLabelPackaging.source, FoodLabelPackaging.label_key).in_(list(labels))
            )
            .order_by(
                FoodLabelPackaging.source,
                FoodLabelPackaging.label_key,
                FoodLabelPackaging.position,
            )
        )
        return rows.scalars().all()
