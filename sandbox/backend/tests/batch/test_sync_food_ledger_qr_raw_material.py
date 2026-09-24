"""Batch job test — sync_food_ledger_qr_raw_material."""

import pytest

import app.batch.sync_food_ledger_qr_raw_material as job_module
from app.batch.sync_food_ledger_qr_raw_material import sync_food_ledger_qr_raw_material
from app.models.food.ledger_qr_raw_material import FoodLedgerQrRawMaterial
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_qr_raw_material_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-qr-raw-material`
    fills `food_ledger_qr_raw_material`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_qr_raw_material,
        job_module,
        FoodLedgerQrRawMaterial,
    )
