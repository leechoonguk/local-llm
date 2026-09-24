"""FoodNutritionService tests — the rebuild off I2790, and the edge to the report it names."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.food.item_report import FoodItemReport
from app.models.food.ledger_nutrition import FoodLedgerNutrition
from app.models.food.nutrition import FoodNutrition
from app.services.food.nutrition import FoodNutritionService


SYNCED_BY = "batch:derive_food_tables"


@pytest.mark.asyncio
async def test_rebuild_copies_the_ledger_whole_and_a_rerun_replaces(factory, pinned) -> None:
    """Every ledger record is a derived record, nutrients included; a rerun writes the same."""
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerNutrition(
                    food_code="D101-004160000-0001",
                    food_name="찐빵",
                    item_report_no="1",
                    energy_kcal=250,
                ),
                FoodLedgerNutrition(food_code="R2-0001", food_name="쌀_백미_생것"),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodNutritionService(session)
        assert await service.rebuild_nutrition(SYNCED_BY) == 2
        assert await service.rebuild_nutrition(SYNCED_BY) == 2

    async with factory() as session:
        rows = (
            (await session.execute(select(FoodNutrition).order_by(FoodNutrition.food_code)))
            .scalars()
            .all()
        )
    assert [(r.food_code, r.item_report_no, r.energy_kcal, r.created_by) for r in rows] == [
        ("D101-004160000-0001", "1", 250, SYNCED_BY),
        ("R2-0001", None, None, SYNCED_BY),
    ]


@pytest.mark.asyncio
async def test_a_report_lists_its_nutrition_records_and_a_record_names_its_report(
    factory,
) -> None:
    """The edge runs both ways on (report_kind, item_report_no); an unknown pair dangles.

    The number alone is not the product: three registries number in their own
    spaces, so the kind the derivation resolved is half of every join.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodItemReport(report_kind="domestic", item_report_no="1", product_name="찐빵"),
                FoodItemReport(report_kind="livestock", item_report_no="2", product_name="소시지"),
                FoodNutrition(
                    food_code="N1", food_name="찐빵", report_kind="domestic", item_report_no="1"
                ),
                FoodNutrition(
                    food_code="N2",
                    food_name="찐빵 (재측정)",
                    report_kind="domestic",
                    item_report_no="1",
                ),
                FoodNutrition(
                    food_code="N3",
                    food_name="솔트",
                    report_kind="domestic",
                    item_report_no="20IT02X00D9",
                ),
                FoodNutrition(food_code="N4", food_name="쌀_백미_생것"),
            ]
        )
        await session.commit()

    async with factory() as session:
        reports = (
            (
                await session.execute(
                    select(FoodItemReport)
                    .options(joinedload(FoodItemReport.nutritions))
                    .order_by(FoodItemReport.item_report_no)
                )
            )
            .unique()
            .scalars()
            .all()
        )
        records = (
            (
                await session.execute(
                    select(FoodNutrition)
                    .options(joinedload(FoodNutrition.item_report))
                    .order_by(FoodNutrition.food_code)
                )
            )
            .scalars()
            .all()
        )

    assert [(r.item_report_no, sorted(n.food_code for n in r.nutritions)) for r in reports] == [
        ("1", ["N1", "N2"]),
        ("2", []),
    ]
    assert [(n.food_code, n.item_report and n.item_report.product_name) for n in records] == [
        ("N1", "찐빵"),
        ("N2", "찐빵"),
        ("N3", None),
        ("N4", None),
    ]
