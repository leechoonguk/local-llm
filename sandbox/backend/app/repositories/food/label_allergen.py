# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.label_allergen import FoodLabelAllergen


# ============================================================
# Classes
# ============================================================


class FoodLabelAllergenRepository:
    """Reads over the derived allergen rows. Nothing here writes: the derive job does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_labels(
        self, labels: Sequence[tuple[str, str]]
    ) -> Sequence[FoodLabelAllergen]:
        """Every allergen the labels asked for declare, in the order they printed.

        One query for a report's labels rather than one per label: a report
        carries at most a handful, and a label at most 11 distinct names
        (measured 2026-09-13)."""
        if not labels:
            return []
        rows = await self.session.execute(
            select(FoodLabelAllergen)
            .where(tuple_(FoodLabelAllergen.source, FoodLabelAllergen.label_key).in_(list(labels)))
            .order_by(
                FoodLabelAllergen.source,
                FoodLabelAllergen.label_key,
                FoodLabelAllergen.position,
            )
        )
        return rows.scalars().all()
