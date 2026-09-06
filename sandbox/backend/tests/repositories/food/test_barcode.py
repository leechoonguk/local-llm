"""FoodBarcodeRepository tests — CRUD and the natural-key lookup the sync matches on."""

from datetime import UTC, datetime

import pytest

from app.repositories.food.barcode import FoodBarcodeRepository
from app.schemas.food.barcode import FoodBarcodeCreateInternal, FoodBarcodeUpdateInternal


BARCODE_NO = "8801234567890"

REPORT_NO = "F2024000123456"


@pytest.mark.asyncio
async def test_food_barcode_repository_crud(factory) -> None:
    """The five operations in sequence, ending with a second delete.

    Deleting twice is the interesting part: the repository reports `False`
    instead of raising, which is what lets the service answer 404.
    """
    async with factory() as session:
        repo = FoodBarcodeRepository(session)
        created = await repo.create(
            FoodBarcodeCreateInternal(
                barcode_no=BARCODE_NO,
                report_no=REPORT_NO,
                product_name="신선배 김치",
                created_by="batch",
            )
        )
        await session.commit()
        row_id = created.id

        got = await repo.get(row_id)
        assert got is not None
        assert got.product_name == "신선배 김치"
        assert len(await repo.list()) == 1

        updated = await repo.update(
            row_id, FoodBarcodeUpdateInternal(product_name="묵은지", updated_by="batch")
        )
        assert updated is not None
        assert updated.product_name == "묵은지"

        assert await repo.delete(row_id) is True
        await session.commit()
        assert await repo.get(row_id) is None
        assert await repo.delete(row_id) is False
        assert await repo.update(row_id, FoodBarcodeUpdateInternal(updated_by="batch")) is None


@pytest.mark.asyncio
async def test_food_barcode_repository_stores_the_source_timestamp(factory) -> None:
    """최종수정일시 is business data on the ledger, not machinery.

    Nothing pages by it any more, so the only thing that must stay true is
    that what the provider said is what the row holds.
    """
    stamped = datetime(2024, 3, 1, tzinfo=UTC)
    async with factory() as session:
        repo = FoodBarcodeRepository(session)
        created = await repo.create(
            FoodBarcodeCreateInternal(
                barcode_no=BARCODE_NO,
                report_no=REPORT_NO,
                source_updated_at=stamped,
                created_by="batch",
            )
        )
        await session.commit()

        stored = await repo.get(created.id)
        assert stored is not None
        assert stored.source_updated_at is not None
        assert stored.source_updated_at.replace(tzinfo=UTC) == stamped
