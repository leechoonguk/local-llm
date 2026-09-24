# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.sorting import ordered
from app.models.food.safety_record import JUDGMENT_FAILED, FoodSafetyRecord
from app.schemas.food.item_report import FoodSafetyRecordFilter


# ============================================================
# Constants
# ============================================================

# The first four characters of `recorded_on` (`20260914`) are its year, which is
# how a reader narrows a list of things that happened.
YEAR_WIDTH = 4


# ============================================================
# Classes
# ============================================================


class FoodSafetyRecordRepository:
    """Reads over the derived record table. Nothing here writes: the derive job does."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        offset: int,
        limit: int,
        filters: FoodSafetyRecordFilter | None = None,
        sort: str | None = None,
        order: str = "asc",
    ) -> Sequence[FoodSafetyRecord]:
        """One page of published events, newest first.

        An event is not the product's own statement but an authority's, and it
        is read by date and kind rather than by product - so this list stands
        on its own screen and orders by the day the registry recorded it.
        """
        narrowed = _apply_filters(select(FoodSafetyRecord), filters)
        ordering = (
            narrowed.order_by(FoodSafetyRecord.recorded_on.desc(), FoodSafetyRecord.record_key)
            if sort is None
            else ordered(narrowed, FoodSafetyRecord, sort, order, FoodSafetyRecord.record_key)
        )
        rows = await self.session.execute(ordering.offset(offset).limit(limit))
        return rows.scalars().all()

    async def count(self, filters: FoodSafetyRecordFilter | None = None) -> int:
        """How many events the same narrowing holds - the page's total."""
        query = _apply_filters(select(func.count()).select_from(FoodSafetyRecord), filters)
        return (await self.session.execute(query)).scalar_one()

    async def distinct_values(self, column: InstrumentedAttribute[str | None]) -> list[str]:
        """Every value one column of the table actually holds, in order.

        The screen's selects are built from this rather than from a typed list:
        a feed that publishes a new 회수등급 or a new institution is offered the
        night it arrives.
        """
        rows = await self.session.execute(
            select(column).where(column.is_not(None)).distinct().order_by(column)
        )
        return [value for (value,) in rows.all() if value]

    async def distinct_years(self) -> list[str]:
        """The years the events fall in, newest first - the 연도 select's options."""
        year = func.substr(FoodSafetyRecord.recorded_on, 1, YEAR_WIDTH)
        rows = await self.session.execute(
            select(year)
            .where(FoodSafetyRecord.recorded_on.is_not(None))
            .distinct()
            .order_by(year.desc())
        )
        return [value for (value,) in rows.all() if value]

    async def list_by_report(
        self, report_kind: str, item_report_no: str, offset: int = 0, limit: int = 100
    ) -> Sequence[FoodSafetyRecord]:
        """One product's events, newest first.

        Ordered by the day the registry recorded them, then by the key, so two
        events of one day come back in a stable order.
        """
        rows = await self.session.execute(
            select(FoodSafetyRecord)
            .where(
                FoodSafetyRecord.report_kind == report_kind,
                FoodSafetyRecord.item_report_no == item_report_no,
            )
            .order_by(FoodSafetyRecord.recorded_on.desc(), FoodSafetyRecord.record_key)
            .offset(offset)
            .limit(limit)
        )
        return rows.scalars().all()

    async def count_by_report(self, report_kind: str, item_report_no: str) -> int:
        """How many records the product carries - the number the detail screen shows."""
        total = await self.session.execute(
            select(func.count())
            .select_from(FoodSafetyRecord)
            .where(
                FoodSafetyRecord.report_kind == report_kind,
                FoodSafetyRecord.item_report_no == item_report_no,
            )
        )
        return total.scalar_one()

    async def summarise_by_report(
        self, report_kind: str, item_report_no: str
    ) -> tuple[int, int, str | None]:
        """(records, failures, the day of the newest) for one product.

        Counted over **every** record of the product, not over the page in hand:
        a summary read off one window would say "0 failed" on page 2 of a
        product whose failure is on page 1.
        """
        totals = await self.session.execute(
            select(
                func.count(),
                func.count().filter(FoodSafetyRecord.judgment_code == JUDGMENT_FAILED),
                func.max(FoodSafetyRecord.recorded_on),
            )
            .select_from(FoodSafetyRecord)
            .where(
                FoodSafetyRecord.report_kind == report_kind,
                FoodSafetyRecord.item_report_no == item_report_no,
            )
        )
        records, failed, latest = totals.one()
        return int(records), int(failed), latest

    async def summarise_by_lots(
        self, report_kind: str, item_report_no: str, lot_dates: Sequence[str]
    ) -> dict[str, tuple[int, int, str | None]]:
        """(records, failures, the recall's grade) per lot of one product.

        A lot is a day: the 제조일자 an authority printed on the event, which on
        an import is the day its declaration's 소비기한 starts. The declarations
        tab asks this for the page of lots it draws, so a reader sees which
        declaration the recall sat on without opening the events.
        """
        if not lot_dates:
            return {}
        totals = await self.session.execute(
            select(
                FoodSafetyRecord.lot_date,
                func.count(),
                func.count().filter(FoodSafetyRecord.judgment_code == JUDGMENT_FAILED),
                func.max(FoodSafetyRecord.grade),
            )
            .where(
                FoodSafetyRecord.report_kind == report_kind,
                FoodSafetyRecord.item_report_no == item_report_no,
                FoodSafetyRecord.lot_date.in_(lot_dates),
            )
            .group_by(FoodSafetyRecord.lot_date)
        )
        return {
            lot: (int(records), int(failed), grade) for lot, records, failed, grade in totals.all()
        }


# ============================================================
# Functions
# ============================================================


def _apply_filters(query: Select[Any], filters: FoodSafetyRecordFilter | None) -> Select[Any]:
    """Narrow a query by each field the caller named, and by nothing else.

    Two kinds again: the vocabularies an authority publishes from (what kind of
    record, what it was judged, which registry, which year) match whole, and the
    names a reader types - a product, a business, a registry number - match a
    fragment.

    **`mapped` is on unless the caller turns it off.** 1,553,789 of the rows
    name no product this database holds - 수거검사 of 농산물 and of 집단급식소,
    and numbers no registry here reports on - and a screen about products cannot
    draw them. They are in the table because the table is where the ledgers are
    read from; they are out of a page because nothing on it could say what they
    are about. `mapped=false` is how a reader asks for them anyway.
    """
    if filters is None:
        return query.where(FoodSafetyRecord.report_kind.is_not(None))
    if filters.mapped:
        query = query.where(FoodSafetyRecord.report_kind.is_not(None))
    for column, value in (
        (FoodSafetyRecord.record_kind, filters.record_kind),
        (FoodSafetyRecord.judgment_code, filters.judgment_code),
        (FoodSafetyRecord.report_kind, filters.report_kind),
    ):
        if value is not None:
            query = query.where(column == value)
    for column, value in (
        (FoodSafetyRecord.item_report_no, filters.item_report_no),
        (FoodSafetyRecord.product_name, filters.product_name),
        (FoodSafetyRecord.business_name, filters.business_name),
    ):
        if value is not None:
            query = query.where(column.ilike(f"%{value}%"))
    if filters.record_year is not None:
        query = query.where(
            func.substr(FoodSafetyRecord.recorded_on, 1, YEAR_WIDTH) == filters.record_year
        )
    if filters.recorded_on_from is not None:
        query = query.where(FoodSafetyRecord.recorded_on >= filters.recorded_on_from)
    if filters.recorded_on_to is not None:
        query = query.where(FoodSafetyRecord.recorded_on <= filters.recorded_on_to)
    return query
