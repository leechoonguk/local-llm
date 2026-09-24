"""FoodLedgerNutritionService tests — CRUD contracts and the ledger upsert the batch runs."""

from decimal import Decimal

import pytest

from app.models.food.ledger_nutrition import FoodLedgerNutrition
from app.services.food.ledger_nutrition import FoodLedgerNutritionService
from tests.services.food.helpers import ledger_rows, pages


FOOD_CODE = "D101-004160000-0001"

SYNCED_BY = "batch:sync_food_nutrition_ledger"


def _record(**overrides: object) -> dict[str, object]:
    """One canonical I2790 record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "row_no": "1",
        "food_code": FOOD_CODE,
        "food_name": "국밥_돼지머리",
        "data_group_code": "D",
        "data_group_name": "음식",
        "category_major_name": "밥류",
        "nutrient_basis_amount": "100g",
        "energy_kcal": "137.000",
        "protein_g": "6.70",
        "sodium_mg": "1,000.000",
        "update_date": "2025-01-23",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_replace_nutrition_ledger_reads_a_thousands_separator(factory, pinned) -> None:
    """The portal writes `1,000.000` into a numeric field.

    Measured on the whole feed (2026-09-05): the comma form appears in the
    amounts, 451 times on the single most common value alone. A bare
    `Decimal(text)` raises `InvalidOperation` on it, and the raise would take
    down the page the record arrived in — 500 foods refused for one comma.
    """
    async with pinned() as session:
        assert await FoodLedgerNutritionService(session).replace_nutrition_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerNutrition)
        assert rows[0].sodium_mg == Decimal("1000.000")
        assert rows[0].energy_kcal == Decimal("137.000")


@pytest.mark.asyncio
async def test_replace_nutrition_ledger_keeps_a_food_whose_amount_is_unreadable(
    factory, pinned
) -> None:
    """An amount nobody can parse costs that measurement, never the food.

    The row still carries its other 156 columns, and a nutrient absent is
    honest where a fabricated `0` would be a number somebody could quote.
    """
    async with pinned() as session:
        assert await FoodLedgerNutritionService(session).replace_nutrition_ledger(
            pages([_record(energy_kcal="측정불가")]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerNutrition)
        assert len(rows) == 1
        assert rows[0].energy_kcal is None
        assert rows[0].protein_g == Decimal("6.70")


@pytest.mark.asyncio
async def test_replace_nutrition_ledger_after_a_second_pass_is_the_second_pass(
    factory, pinned
) -> None:
    """A re-sent row is written again, under the id its key mints.

    Every night writes the whole feed over the ledger, so the second pass
    counts its row as written like the first; what a reader may hold on to
    is the `id`, which comes from the natural key and not from the night.
    """
    async with pinned() as session:
        assert await FoodLedgerNutritionService(session).replace_nutrition_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerNutrition)

    async with pinned() as session:
        assert await FoodLedgerNutritionService(session).replace_nutrition_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerNutrition)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_replace_nutrition_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A measurement the portal revised is what the ledger exists to carry."""
    async with pinned() as session:
        await FoodLedgerNutritionService(session).replace_nutrition_ledger(
            pages([_record()]), SYNCED_BY
        )

    async with pinned() as session:
        assert await FoodLedgerNutritionService(session).replace_nutrition_ledger(
            pages([_record(energy_kcal="141.000", update_date="2025-06-01")]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerNutrition)
        assert rows[0].energy_kcal == Decimal("141.000")
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_replace_nutrition_ledger_skips_records_without_a_food_code(factory, pinned) -> None:
    """A record with no key cannot be matched again, so it must not be stored."""
    async with pinned() as session:
        assert await FoodLedgerNutritionService(session).replace_nutrition_ledger(
            pages([_record(), _record(food_code="   "), _record(food_code=None), "not-a-record"]),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerNutrition)) == 1


@pytest.mark.asyncio
async def test_replace_nutrition_ledger_ignores_the_page_position(factory, pinned) -> None:
    """`row_no` is where the record sat in its page, not a fact about the food.

    Stored, it would be a column the feed shifting by one row changes on
    every record - a position in a page, kept as if it were a reading.
    """
    async with pinned() as session:
        assert await FoodLedgerNutritionService(session).replace_nutrition_ledger(
            pages([_record(row_no="947")]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (row,) = await ledger_rows(session, FoodLedgerNutrition)
        assert not hasattr(row, "row_no")
