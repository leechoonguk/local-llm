"""Batch job test — sync_food_ledger_common_standard_type."""

import pytest

import app.batch.sync_food_ledger_common_standard_type as job_module
from app.batch.sync_food_ledger_common_standard_type import sync_food_ledger_common_standard_type
from app.models.food.ledger_common_standard_type import FoodLedgerCommonStandardType
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_common_standard_type_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-common-standard-type`
    fills `food_ledger_common_standard_type`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_common_standard_type,
        job_module,
        FoodLedgerCommonStandardType,
    )
