# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.label import FoodLabel


# ============================================================
# Classes
# ============================================================


class FoodLabelRepository:
    """Reads over the derived label table. Nothing here writes: the derive job does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_item_report_no(self, item_report_no: str) -> Sequence[FoodLabel]:
        """Every label printed under one 품목보고번호, 푸드QR first then HACCP.

        A list because a report is labelled more than once - by two portals, and
        by several packages within one: measured 2026-09-13, the two feeds carry
        19,429 labels over 9,750 reports.

        The order is the source's: 푸드QR is the structured publication (여부
        플래그, 유효기간, 보관방법 in their own columns) and HACCP is the wider
        one, so a screen that shows one shows that one.
        """
        rows = await self.session.execute(
            select(FoodLabel)
            .where(FoodLabel.item_report_no == item_report_no)
            .order_by(FoodLabel.source, FoodLabel.label_key)
        )
        return rows.scalars().all()
