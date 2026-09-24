"""Batch job test — sync_food_ledger_qr_label."""

import pytest

import app.batch.sync_food_ledger_qr_label as job_module
from app.batch.sync_food_ledger_qr_label import sync_food_ledger_qr_label
from app.models.food.ledger_qr_label import FoodLedgerQrLabel
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_qr_label_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-qr-label`
    fills `food_ledger_qr_label`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_qr_label,
        job_module,
        FoodLedgerQrLabel,
    )
