"""Batch job test — sync_food_ledger_livestock_item_report_raw_material."""

import pytest

import app.batch.sync_food_ledger_livestock_item_report_raw_material as job_module
from app.batch.sync_food_ledger_livestock_item_report_raw_material import (
    sync_food_ledger_livestock_item_report_raw_material,
)
from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial,
)
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_livestock_item_report_raw_material_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-livestock-item-report-raw-material`
    fills `food_ledger_livestock_item_report_raw_material`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_livestock_item_report_raw_material,
        job_module,
        FoodLedgerLivestockItemReportRawMaterial,
    )
