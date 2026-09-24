# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food.item_report_declaration import FoodItemReportDeclaration


# ============================================================
# Classes
# ============================================================


class FoodItemReportDeclarationRepository:
    """Reads over the derived declaration table. Nothing here writes: the derive job does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_report(
        self, report_kind: str, item_report_no: str, offset: int = 0, limit: int = 100
    ) -> Sequence[FoodItemReportDeclaration]:
        """One product's declarations, newest first - by 처리일자 or by 보고년도.

        Two kinds share the table and each dates itself in its own column, so
        the order reads whichever the row filled: a 수입신고 has a 처리일자 and
        a 생산실적 has a 보고년도, never both. Paged because the widest product
        carries 1,388 of them (2026-09-14).
        """
        rows = await self.session.execute(
            select(FoodItemReportDeclaration)
            .where(
                FoodItemReportDeclaration.report_kind == report_kind,
                FoodItemReportDeclaration.item_report_no == item_report_no,
            )
            .order_by(
                func.coalesce(
                    FoodItemReportDeclaration.processed_date,
                    FoodItemReportDeclaration.report_year,
                ).desc(),
                FoodItemReportDeclaration.declaration_key,
            )
            .offset(offset)
            .limit(limit)
        )
        return rows.scalars().all()

    async def count_by_report(self, report_kind: str, item_report_no: str) -> int:
        """How many times the product was declared - the number the detail screen shows."""
        total = await self.session.execute(
            select(func.count())
            .select_from(FoodItemReportDeclaration)
            .where(
                FoodItemReportDeclaration.report_kind == report_kind,
                FoodItemReportDeclaration.item_report_no == item_report_no,
            )
        )
        return total.scalar_one()
