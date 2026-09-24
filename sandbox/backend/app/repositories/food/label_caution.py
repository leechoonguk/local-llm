# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.label_caution import FoodLabelCaution


# ============================================================
# Classes
# ============================================================


class FoodLabelCautionRepository:
    """Reads over the derived 주의사항 rows. Nothing here writes: the derive job does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_labels(self, labels: Sequence[tuple[str, str]]) -> Sequence[FoodLabelCaution]:
        """Every 주의사항 문구 of the labels asked for, in printed order.

        Only 푸드QR publishes them, so a HACCP label answers none (8,134 rows
        over 2,154 라벨, measured 2026-09-13)."""
        if not labels:
            return []
        rows = await self.session.execute(
            select(FoodLabelCaution)
            .where(tuple_(FoodLabelCaution.source, FoodLabelCaution.label_key).in_(list(labels)))
            .order_by(
                FoodLabelCaution.source,
                FoodLabelCaution.label_key,
                FoodLabelCaution.position,
            )
        )
        return rows.scalars().all()
