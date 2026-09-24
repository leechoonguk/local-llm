"""FoodCommonStandardTypeService tests — the rebuild off I2590, and the heading tree."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.models.food.common_standard_type import FoodCommonStandardType
from app.models.food.ledger_common_standard_type import FoodLedgerCommonStandardType
from app.services.food.common_standard_type import FoodCommonStandardTypeService


SYNCED_BY = "batch:derive_food_tables"


@pytest.mark.asyncio
async def test_rebuild_copies_the_outline_and_a_heading_names_the_one_above_it(
    factory, pinned
) -> None:
    """Every ledger heading is a derived heading; `parent` walks one step up the outline."""
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerCommonStandardType(
                    common_standard_type_code="000095",
                    standard_name="식품의 기준 및 규격",
                    level="1",
                ),
                FoodLedgerCommonStandardType(
                    common_standard_type_code="000096",
                    standard_name="제2. 식품일반에 대한 공통기준 및 규격",
                    parent_common_standard_type_code="000095",
                    level="2",
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodCommonStandardTypeService(session)
        assert await service.rebuild_common_standard_type(SYNCED_BY) == 2
        assert await service.rebuild_common_standard_type(SYNCED_BY) == 2

    async with factory() as session:
        parent = aliased(FoodCommonStandardType)
        rows = (
            await session.execute(
                select(FoodCommonStandardType.standard_name, parent.standard_name)
                .outerjoin(FoodCommonStandardType.parent.of_type(parent))
                .order_by(FoodCommonStandardType.common_standard_type_code)
            )
        ).all()
    assert [tuple(r) for r in rows] == [
        ("식품의 기준 및 규격", None),
        ("제2. 식품일반에 대한 공통기준 및 규격", "식품의 기준 및 규격"),
    ]
