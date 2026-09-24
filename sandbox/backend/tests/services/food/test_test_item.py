"""FoodTestItemService tests — the rebuild off I2570."""

import pytest
from sqlalchemy import select

from app.models.food.ledger_test_item import FoodLedgerTestItem
from app.models.food.test_item import FoodTestItem
from app.services.food.test_item import FoodTestItemService


SYNCED_BY = "batch:derive_food_tables"


@pytest.mark.asyncio
async def test_rebuild_copies_the_ledger_whole_and_a_rerun_replaces(factory, pinned) -> None:
    """Every ledger item is a derived item, column for column."""
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerTestItem(test_item_code="C10001", korean_name="수분", in_use="Y"),
                FoodLedgerTestItem(test_item_code="C10002", korean_name="회분", in_use="N"),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodTestItemService(session)
        assert await service.rebuild_test_item(SYNCED_BY) == 2
        assert await service.rebuild_test_item(SYNCED_BY) == 2

    async with factory() as session:
        rows = (
            (await session.execute(select(FoodTestItem).order_by(FoodTestItem.test_item_code)))
            .scalars()
            .all()
        )
    assert [(r.test_item_code, r.korean_name, r.in_use, r.created_by) for r in rows] == [
        ("C10001", "수분", "Y", SYNCED_BY),
        ("C10002", "회분", "N", SYNCED_BY),
    ]
