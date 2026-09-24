"""Batch job test — sync_food_ledger_barcode."""

import pytest

import app.batch.sync_food_ledger_barcode as job_module
from app.batch.sync_food_ledger_barcode import sync_food_ledger_barcode
from app.models.food.ledger_barcode import FoodLedgerBarcode
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_barcode_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-barcode-product-info`
    fills `food_ledger_barcode`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_barcode,
        job_module,
        FoodLedgerBarcode,
    )
