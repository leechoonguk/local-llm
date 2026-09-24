"""Batch job test — sync_food_ledger_admin_disposition."""

import pytest

import app.batch.sync_food_ledger_admin_disposition as job_module
from app.batch.sync_food_ledger_admin_disposition import sync_food_ledger_admin_disposition
from app.models.food.ledger_admin_disposition import FoodLedgerAdminDisposition
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_admin_disposition_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-admin-disposition` fills `food_ledger_admin_disposition`:
    251 rows in one window (2026-09-18).
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_admin_disposition,
        job_module,
        FoodLedgerAdminDisposition,
    )
