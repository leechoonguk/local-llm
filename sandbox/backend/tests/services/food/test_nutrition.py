"""FoodNutritionService tests — CRUD contracts and the ledger upsert the batch runs."""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.schemas.food.nutrition import (
    FoodNutritionCreateRequest,
    FoodNutritionUpdateRequest,
    to_read,
    to_read_list,
)
from app.services.food.nutrition import FoodNutritionService
from tests.services.food.helpers import pages


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
async def test_food_nutrition_service_crud(factory) -> None:
    """Each step runs in its own session, as the request lifecycle does."""
    async with factory() as session:
        created = await FoodNutritionService(session).create_nutrition(
            FoodNutritionCreateRequest(food_code=FOOD_CODE, food_name="국밥"),
            created_by="tester",
        )
        row_id = created.id

    async with factory() as session:
        stored = await FoodNutritionService(session).get_nutrition(row_id)
        assert stored.food_name == "국밥"
        assert to_read(stored).food_code == FOOD_CODE

    async with factory() as session:
        rows = await FoodNutritionService(session).list_nutritions()
        assert len(to_read_list(rows)) == 1

    async with factory() as session:
        updated = await FoodNutritionService(session).update_nutrition(
            row_id, FoodNutritionUpdateRequest(food_name="돼지국밥"), updated_by="tester"
        )
        assert updated.food_name == "돼지국밥"

    async with factory() as session:
        await FoodNutritionService(session).delete_nutrition(row_id)

    async with factory() as session:
        assert await FoodNutritionService(session).list_nutritions() == []


@pytest.mark.asyncio
async def test_food_nutrition_service_missing_row_raises_not_found(factory) -> None:
    """404 is the ledger's answer for an id it does not hold, on all three verbs."""
    missing = uuid4()
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await FoodNutritionService(session).get_nutrition(missing)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await FoodNutritionService(session).update_nutrition(
                missing, FoodNutritionUpdateRequest(food_name="x"), updated_by="tester"
            )

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await FoodNutritionService(session).delete_nutrition(missing)


@pytest.mark.asyncio
async def test_replace_nutrition_ledger_reads_a_thousands_separator(factory, pinned) -> None:
    """The portal writes `1,000.000` into a numeric field.

    Measured on the whole feed (2026-09-05): the comma form appears in the
    amounts, 451 times on the single most common value alone. A bare
    `Decimal(text)` raises `InvalidOperation` on it, and the raise would take
    down the page the record arrived in — 500 foods refused for one comma.
    """
    async with pinned() as session:
        assert await FoodNutritionService(session).replace_nutrition_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await FoodNutritionService(session).list_nutritions()
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
        assert await FoodNutritionService(session).replace_nutrition_ledger(
            pages([_record(energy_kcal="측정불가")]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await FoodNutritionService(session).list_nutritions()
        assert len(rows) == 1
        assert rows[0].energy_kcal is None
        assert rows[0].protein_g == Decimal("6.70")


@pytest.mark.asyncio
async def test_replace_nutrition_ledger_inserts_then_leaves_unchanged_rows_alone(
    factory, pinned
) -> None:
    """A pass that re-sends a row unchanged must not rewrite it.

    Every night reads the whole feed, so a merge that always wrote would bump
    `version` and `updated_at` on every row of the ledger - and "this row
    changed" would stop meaning anything.
    """
    async with pinned() as session:
        assert await FoodNutritionService(session).replace_nutrition_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with pinned() as session:
        assert await FoodNutritionService(session).replace_nutrition_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 0)

    async with factory() as session:
        rows = await FoodNutritionService(session).list_nutritions()
        assert len(rows) == 1
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_replace_nutrition_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A measurement the portal revised is what the ledger exists to carry."""
    async with pinned() as session:
        await FoodNutritionService(session).replace_nutrition_ledger(pages([_record()]), SYNCED_BY)

    async with pinned() as session:
        assert await FoodNutritionService(session).replace_nutrition_ledger(
            pages([_record(energy_kcal="141.000", update_date="2025-06-01")]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await FoodNutritionService(session).list_nutritions()
        assert rows[0].energy_kcal == Decimal("141.000")
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_replace_nutrition_ledger_skips_records_without_a_food_code(factory, pinned) -> None:
    """A record with no key cannot be matched again, so it must not be stored."""
    async with pinned() as session:
        assert await FoodNutritionService(session).replace_nutrition_ledger(
            pages([_record(), _record(food_code="   "), _record(food_code=None), "not-a-record"]),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        assert len(await FoodNutritionService(session).list_nutritions()) == 1


@pytest.mark.asyncio
async def test_replace_nutrition_ledger_ignores_the_page_position(pinned) -> None:
    """`row_no` is where the record sat in its page, not a fact about the food.

    Stored, it would differ the moment the feed shifts by one row and every
    later run would rewrite the whole ledger to record a new position.
    """
    async with pinned() as session:
        await FoodNutritionService(session).replace_nutrition_ledger(pages([_record()]), SYNCED_BY)

    async with pinned() as session:
        assert await FoodNutritionService(session).replace_nutrition_ledger(
            pages([_record(row_no="947")]), SYNCED_BY
        ) == (1, 0)
