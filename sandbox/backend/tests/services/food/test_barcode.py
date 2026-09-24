"""FoodBarcodeService tests — the rebuild off the C005 ledger."""

import pytest
from sqlalchemy import select

from app.models.food.barcode import FoodBarcode
from app.models.food.ledger_barcode import FoodLedgerBarcode
from app.services.food.barcode import FoodBarcodeService


SYNCED_BY = "batch:derive_food_tables"


@pytest.mark.asyncio
async def test_rebuild_copies_the_ledger_whole_and_a_rerun_replaces(factory, pinned) -> None:
    """Every ledger pair is a derived row, column for column."""
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerBarcode(
                    barcode_no="8805522061018",
                    item_report_no="19950129282236",
                    product_name="좋은상품 유기농 부침가루",
                    product_type_name="기타가공품",
                ),
                FoodLedgerBarcode(
                    barcode_no="8805522061025",
                    item_report_no="19950129282236",
                    product_name="좋은상품 유기농 튀김가루",
                    product_type_name="기타가공품",
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodBarcodeService(session)
        assert await service.rebuild_barcode(SYNCED_BY) == 2
        assert await service.rebuild_barcode(SYNCED_BY) == 2

    async with factory() as session:
        rows = (
            (await session.execute(select(FoodBarcode).order_by(FoodBarcode.barcode_no)))
            .scalars()
            .all()
        )
    assert [(r.barcode_no, r.item_report_no, r.product_name, r.created_by) for r in rows] == [
        ("8805522061018", "19950129282236", "좋은상품 유기농 부침가루", SYNCED_BY),
        ("8805522061025", "19950129282236", "좋은상품 유기농 튀김가루", SYNCED_BY),
    ]
