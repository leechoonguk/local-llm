"""Batch job tests - sync_mfds_ledgers against an in-memory engine.

The provider is scripted at the walk: the job's contract is which feeds it
reads, what its ledgers hold afterwards, what it records per window, and how
one feed's failure reaches the run - not what the network answered.
"""

from __future__ import annotations

import pytest

import app.batch.sync_mfds_ledgers as job
from app.core.exceptions import IntegrationError, LedgerFloorError
from app.models.food.barcode import FoodBarcode
from app.models.food.item_report import FoodItemReport
from app.models.food.item_report_raw_material import FoodItemReportRawMaterial
from app.models.food.product_classification import FoodProductClassification
from app.models.food.raw_material import FoodRawMaterial
from app.models.food.test_item import FoodTestItem
from app.services.batch.run import current_run_id
from tests.batch.scripted import rows, run_in_context, script_walk, steps, swapped_engine


TEST_ITEM, PRODUCT_CLASSIFICATION, RAW_MATERIAL, BARCODE, ITEM_REPORT, ITEM_REPORT_RAW_MATERIAL = (
    feed.operation_code for feed in job.FEEDS
)


def _test_item(index: int) -> dict[str, object]:
    return {"test_item_code": f"A{index}", "korean_name": "가용성염류"}


def _product_classification(index: int) -> dict[str, object]:
    return {"product_code": f"A{index}", "korean_name": "곡류"}


def _barcode(index: int, **overrides: object) -> dict[str, object]:
    return {"barcode_no": f"880{index}", "report_no": "F1", "product_name": "김치", **overrides}


def _raw_material(index: int) -> dict[str, object]:
    return {"raw_material_code": f"RM{index}", "representative_raw_material_name": "배추"}


def _item_report(index: int) -> dict[str, object]:
    return {"item_report_no": f"IR{index}", "product_name": "김치"}


def _item_report_raw_material(index: int) -> dict[str, object]:
    return {"item_report_no": f"IR{index}", "raw_material_names": "배추, 소금"}


def _every_feed(barcode=None, raw_material=None, item_report=None, item_report_raw_material=None):
    """One short page per feed - a whole pass of each - unless a test says otherwise."""
    return {
        TEST_ITEM: [[_test_item(1)]],
        PRODUCT_CLASSIFICATION: [[_product_classification(1)]],
        BARCODE: barcode or [[_barcode(1), _barcode(2), _barcode(3)]],
        RAW_MATERIAL: raw_material or [[_raw_material(1)]],
        ITEM_REPORT: item_report or [[_item_report(1)]],
        ITEM_REPORT_RAW_MATERIAL: item_report_raw_material or [[_item_report_raw_material(1)]],
    }


@pytest.fixture()
async def test_engine():
    """The job module's engine, swapped for an in-memory one; no run in context."""
    current_run_id.set(None)
    async with swapped_engine(job) as engine:
        yield engine


@pytest.mark.asyncio
async def test_every_feed_is_walked_whole_and_its_ledger_made_equal_to_the_pass(
    test_engine, monkeypatch
) -> None:
    """Six feeds, one rule: windows of PAGE_SIZE from row 1 until a short page."""
    full_page = [_barcode(index) for index in range(1, job.PAGE_SIZE + 1)]
    asked = script_walk(
        monkeypatch, "RANGE", _every_feed(barcode=[full_page, [_barcode(job.PAGE_SIZE + 1)]])
    )

    assert await job.sync_mfds_ledgers() == job.PAGE_SIZE + 6

    # Smallest first, so a night that runs out of quota still finished something.
    assert [code for code, _ in asked] == [
        TEST_ITEM,
        PRODUCT_CLASSIFICATION,
        RAW_MATERIAL,
        BARCODE,
        BARCODE,
        ITEM_REPORT,
        ITEM_REPORT_RAW_MATERIAL,
    ]
    assert asked[3][1] == {"range_start": 1, "range_end": job.PAGE_SIZE}
    assert asked[4][1] == {"range_start": job.PAGE_SIZE + 1, "range_end": 2 * job.PAGE_SIZE}
    assert len(await rows(test_engine, FoodTestItem)) == 1
    assert len(await rows(test_engine, FoodProductClassification)) == 1
    assert len(await rows(test_engine, FoodBarcode)) == job.PAGE_SIZE + 1
    assert len(await rows(test_engine, FoodRawMaterial)) == 1
    assert len(await rows(test_engine, FoodItemReport)) == 1
    assert len(await rows(test_engine, FoodItemReportRawMaterial)) == 1
    assert {row.created_by for row in await rows(test_engine, FoodBarcode)} == {job.SYNCED_BY}


@pytest.mark.asyncio
async def test_the_next_night_reads_the_whole_feed_again_and_changes_only_what_moved(
    test_engine, monkeypatch
) -> None:
    """No cursor: the second pass asks for row 1 again, and the ledger follows the feed."""
    script_walk(monkeypatch, "RANGE", _every_feed())
    await job.sync_mfds_ledgers()
    ids = {row.barcode_no: row.id for row in await rows(test_engine, FoodBarcode)}

    # Row 1 unchanged, row 2 renamed, row 3 gone, row 4 new: three changes.
    asked = script_walk(
        monkeypatch,
        "RANGE",
        _every_feed(barcode=[[_barcode(1), _barcode(2, product_name="묵은지"), _barcode(4)]]),
    )
    assert await job.sync_mfds_ledgers() == 3
    assert asked[0][1]["range_start"] == 1
    after = {row.barcode_no: row for row in await rows(test_engine, FoodBarcode)}
    assert set(after) == {"8801", "8802", "8804"}
    assert after["8801"].id == ids["8801"] and after["8801"].version == 1
    assert after["8802"].id == ids["8802"] and after["8802"].version == 2


@pytest.mark.asyncio
async def test_each_window_is_recorded_as_a_step_numbered_across_feeds(
    test_engine, monkeypatch
) -> None:
    """A run says the night worked; the steps say which windows it walked."""
    full_page = [_barcode(index) for index in range(1, job.PAGE_SIZE + 1)]
    script_walk(
        monkeypatch, "RANGE", _every_feed(barcode=[full_page, [_barcode(job.PAGE_SIZE + 1)]])
    )
    await run_in_context(test_engine, "sync_mfds_ledgers")

    await job.sync_mfds_ledgers()

    recorded = await steps(test_engine)
    assert [(s.sequence, s.range_start, s.range_end, s.received) for s in recorded] == [
        (1, 1, job.PAGE_SIZE, 1),
        (2, 1, job.PAGE_SIZE, 1),
        (3, 1, job.PAGE_SIZE, 1),
        (4, 1, job.PAGE_SIZE, job.PAGE_SIZE),
        (5, job.PAGE_SIZE + 1, 2 * job.PAGE_SIZE, 1),
        (6, 1, job.PAGE_SIZE, 1),
        (7, 1, job.PAGE_SIZE, 1),
    ]
    assert {s.status for s in recorded} == {"SUCCEEDED"}
    # A merge changes rows per feed, not per window: no step claims a count.
    assert {s.written for s in recorded} == {None}


@pytest.mark.asyncio
async def test_a_job_started_by_hand_records_no_step(test_engine, monkeypatch) -> None:
    """A step without a run has nothing to belong to."""
    script_walk(monkeypatch, "RANGE", _every_feed())
    await job.sync_mfds_ledgers()
    assert await steps(test_engine) == []


@pytest.mark.asyncio
async def test_a_feed_that_fails_leaves_its_ledger_and_the_others_get_their_turn(
    test_engine, monkeypatch
) -> None:
    """One provider refusal is one feed's night, not the run's.

    The refused feed keeps yesterday's ledger, the failing window is recorded
    as the step it would have been, the remaining feeds are still replaced -
    and the run reads FAILED, because the first failure is raised at the end.
    """
    script_walk(monkeypatch, "RANGE", _every_feed())
    await job.sync_mfds_ledgers()

    refusal = IntegrationError(
        job.PROVIDER_CODE, RAW_MATERIAL, "External API error: HTTP 503", status_code=503
    )
    script_walk(
        monkeypatch,
        "RANGE",
        _every_feed(
            barcode=[[_barcode(1), _barcode(2)]],
            raw_material=[[_raw_material(1)] * job.PAGE_SIZE, refusal],
            item_report=[[_item_report(1), _item_report(2)]],
        ),
    )
    await run_in_context(test_engine, "sync_mfds_ledgers")

    with pytest.raises(IntegrationError, match="HTTP 503"):
        await job.sync_mfds_ledgers()

    # Before the refusal: barcode replaced (3 -> 2). After it: item report grew (1 -> 2).
    assert len(await rows(test_engine, FoodBarcode)) == 2
    assert len(await rows(test_engine, FoodRawMaterial)) == 1
    assert len(await rows(test_engine, FoodItemReport)) == 2
    failed = [s for s in await steps(test_engine) if s.status == "FAILED"]
    assert [(s.range_start, s.range_end, s.error_code) for s in failed] == [
        (job.PAGE_SIZE + 1, 2 * job.PAGE_SIZE, "IntegrationError")
    ]
    assert failed[0].error_detail == "External API error: HTTP 503"


@pytest.mark.asyncio
async def test_a_pass_under_the_floor_is_a_failed_feed(test_engine, monkeypatch) -> None:
    """A provider answering empty pages must not empty the ledger."""
    script_walk(monkeypatch, "RANGE", _every_feed())
    await job.sync_mfds_ledgers()

    script_walk(monkeypatch, "RANGE", _every_feed(barcode=[[]]))
    with pytest.raises(LedgerFloorError, match="food_barcode"):
        await job.sync_mfds_ledgers()
    assert len(await rows(test_engine, FoodBarcode)) == 3
