"""FoodCommonStandardExclusionService tests — the rebuild off I2610, and the tier it hangs on."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.food.common_standard_exclusion import FoodCommonStandardExclusion
from app.models.food.ledger_common_standard_exclusion import FoodLedgerCommonStandardExclusion
from app.models.food.product_classification import FoodProductClassification
from app.services.food.common_standard_exclusion import FoodCommonStandardExclusionService


SYNCED_BY = "batch:derive_food_tables"


@pytest.mark.asyncio
async def test_rebuild_copies_the_ledger_and_a_tier_lists_its_exemptions(factory, pinned) -> None:
    """Every ledger exemption is a derived one, and the tier it is written on lists it."""
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerCommonStandardExclusion(
                    common_standard_type_code="000140",
                    product_code="C0000000000000",
                    test_item_code="C20001",
                    standard_name="가공식품 제외",
                ),
                FoodProductClassification(
                    product_code="C0000000000000", korean_name="가공식품", product_yn="N"
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodCommonStandardExclusionService(session)
        assert await service.rebuild_common_standard_exclusion(SYNCED_BY) == 1
        assert await service.rebuild_common_standard_exclusion(SYNCED_BY) == 1

    async with factory() as session:
        (tier,) = (
            (
                await session.execute(
                    select(FoodProductClassification).options(
                        joinedload(FoodProductClassification.common_standard_exclusions)
                    )
                )
            )
            .unique()
            .scalars()
            .all()
        )
        (row,) = (
            (
                await session.execute(
                    select(FoodCommonStandardExclusion).options(
                        joinedload(FoodCommonStandardExclusion.classification)
                    )
                )
            )
            .scalars()
            .all()
        )
    assert [e.standard_name for e in tier.common_standard_exclusions] == ["가공식품 제외"]
    assert row.classification is not None and row.classification.korean_name == "가공식품"
