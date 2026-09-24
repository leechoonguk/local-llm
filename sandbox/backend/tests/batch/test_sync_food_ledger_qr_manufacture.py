"""Batch job test — sync_food_ledger_qr_manufacture."""

import pytest

import app.batch.sync_food_ledger_qr_manufacture as job_module
from app.batch.sync_food_ledger_qr_manufacture import sync_food_ledger_qr_manufacture
from app.models.food.ledger_qr_manufacture import FoodLedgerQrManufacture
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_qr_manufacture_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-qr-manufacture`
    fills `food_ledger_qr_manufacture`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_qr_manufacture,
        job_module,
        FoodLedgerQrManufacture,
    )
