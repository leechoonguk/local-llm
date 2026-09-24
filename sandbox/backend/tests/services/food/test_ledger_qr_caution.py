"""FoodLedgerQrCautionService tests - the ledger the data.go.kr batch replaces."""

import pytest

from app.models.food.ledger_qr_caution import FoodLedgerQrCaution
from app.services.food.ledger_qr_caution import FoodLedgerQrCautionService
from tests.services.food.helpers import ledger_rows, pages


SYNCED_BY = "batch:sync_data_go_kr_ledgers"


def _service(session) -> FoodLedgerQrCautionService:
    return FoodLedgerQrCautionService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "label_no": "202410221000001856",
        "detail_serial": "1000000001645",
        "caution_text": "부정·불량식품신고는국번없이1399\n",
        "product_name": "전복삼계죽 420g",
        "barcode_no": "08801007901244",
        "version_no": "1",
        "valid_from": "20241101",
        "valid_to": "99991231",
        "source_updated_at": "2026-07-30 19:03:34",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_qr_caution_after_a_second_pass_is_the_second_pass(factory, pinned) -> None:
    """A re-sent row is written again, under the id its key mints."""
    async with pinned() as session:
        assert await _service(session).replace_qr_caution_ledger(pages([_record()]), SYNCED_BY) == (
            1,
            1,
        )

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerQrCaution)

    async with pinned() as session:
        assert await _service(session).replace_qr_caution_ledger(pages([_record()]), SYNCED_BY) == (
            1,
            1,
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerQrCaution)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_qr_caution_skips_records_without_a_key(factory, pinned) -> None:
    """A record missing its key cannot be matched again, so it must not be stored."""
    async with pinned() as session:
        assert await _service(session).replace_qr_caution_ledger(
            pages(
                [
                    _record(),
                    _record(label_no=None),
                    _record(detail_serial=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerQrCaution)) == 1
