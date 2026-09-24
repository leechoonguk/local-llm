"""FoodLedgerQrAllergyService tests - the ledger the 푸드QR feed replaces every night."""

import pytest

from app.models.food.ledger_qr_allergy import FoodLedgerQrAllergy
from app.services.food.ledger_qr_allergy import FoodLedgerQrAllergyService
from tests.services.food.helpers import ledger_rows, pages


SYNCED_BY = "batch:sync_data_go_kr_ledgers"


def _service(session) -> FoodLedgerQrAllergyService:
    return FoodLedgerQrAllergyService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical 알레르기정보 record - one declared allergen of one label."""
    record: dict[str, object] = {
        "label_no": "202608311000011550",
        "allergen_serial": "1000000051518",
        "allergen_name": "밀",
        "item_report_serial": "1000000038418",
        "barcode_no": "02700038883184",
        "product_name": "버라이어티샌드위치",
        "label_group_name": "한국데리카후레쉬",
        "version_no": "8",
        "valid_from": "20260831",
        "valid_to": "99991231",
        "source_updated_at": "2026-08-31 15:50:02",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_ledger_qr_allergy_after_a_second_pass_is_the_second_pass(factory, pinned) -> None:
    """A re-sent row is written again, under the id its key mints."""
    async with pinned() as session:
        assert await _service(session).replace_qr_allergy_ledger(pages([_record()]), SYNCED_BY) == (
            1,
            1,
        )

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerQrAllergy)

    async with pinned() as session:
        assert await _service(session).replace_qr_allergy_ledger(pages([_record()]), SYNCED_BY) == (
            1,
            1,
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerQrAllergy)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_ledger_qr_allergy_skips_records_without_a_key(factory, pinned) -> None:
    """A record missing its key cannot be matched again, so it must not be stored."""
    async with pinned() as session:
        assert await _service(session).replace_qr_allergy_ledger(
            pages(
                [
                    _record(),
                    _record(label_no="   "),
                    _record(allergen_serial=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerQrAllergy)) == 1


@pytest.mark.asyncio
async def test_ledger_qr_allergy_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 최종수정일시 costs that column, never the record."""
    async with pinned() as session:
        await _service(session).replace_qr_allergy_ledger(
            pages([_record(source_updated_at="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerQrAllergy)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
        assert rows[0].allergen_name == _record()["allergen_name"]
