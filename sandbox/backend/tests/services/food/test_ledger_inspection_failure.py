"""FoodLedgerInspectionFailureService tests - the 검사부적합 ledger the mfds batch replaces."""

import pytest

from app.models.food.ledger_inspection_failure import FoodLedgerInspectionFailure
from app.services.food.ledger_inspection_failure import FoodLedgerInspectionFailureService
from tests.services.food.helpers import ledger_rows, pages


SYNCED_BY = "batch:sync_mfds_ledgers"


def _record(**overrides: object) -> dict[str, object]:
    """One canonical record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "disposal_seq": "3000222960",
        "test_item_name": "프로사이미돈",
        "standard_text": "5.0 mg/kg 이하",
        "test_result_text": "20.2 mg/kg",
        "institution_name": "울산광역시 보건환경연구원",
        "item_report_no": "",
        "license_no": "",
        "product_name": "부추(L23)",
        "business_name": "전*복",
        "address": "울산광역시 울주군",
        "barcode_no": "21000309959510025009",
        "packaging_unit": "",
        "manufactured_text": "20260309",
        "shelf_life_text": "",
        "product_type_name": "부추",
        "registered_on": "2026.03.11",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_one_disposal_carries_one_row_per_failed_item(factory, pinned) -> None:
    """572 rows over 479 serials (2026-09-14): the key is the triple, not the serial.

    Four 농약 on one 로즈마리 are four rows, and one item judged against two
    standards is two - which is why the standard is part of the key.
    """
    async with pinned() as session:
        assert await FoodLedgerInspectionFailureService(session).replace_inspection_failure_ledger(
            pages(
                [
                    _record(),
                    _record(test_item_name="플루디옥소닐"),
                    _record(standard_text="0.01 mg/kg 이하 (기준 규격 없음)"),
                ]
            ),
            SYNCED_BY,
        ) == (3, 3)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerInspectionFailure)
        assert len({row.disposal_seq for row in rows}) == 1
        assert len(rows) == 3


@pytest.mark.asyncio
async def test_a_row_the_portal_sends_twice_is_written_once(factory, pinned) -> None:
    """Two of the feed's 572 rows are identical in all eighteen columns."""
    async with pinned() as session:
        assert await FoodLedgerInspectionFailureService(session).replace_inspection_failure_ledger(
            pages([_record(), _record()]), SYNCED_BY
        ) == (2, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerInspectionFailure)) == 1


@pytest.mark.asyncio
async def test_inspection_failure_skips_records_without_a_key(factory, pinned) -> None:
    """Any part of the triple missing means a row no later pass can match."""
    async with pinned() as session:
        assert await FoodLedgerInspectionFailureService(session).replace_inspection_failure_ledger(
            pages(
                [
                    _record(),
                    _record(disposal_seq=None),
                    _record(test_item_name=None),
                    _record(standard_text=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (5, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerInspectionFailure)) == 1
