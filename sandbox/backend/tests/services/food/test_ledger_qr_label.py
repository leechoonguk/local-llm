"""FoodLedgerQrLabelService tests - the ledger the 푸드QR feed replaces every night."""

import pytest

from app.models.food.ledger_qr_label import FoodLedgerQrLabel
from app.services.food.ledger_qr_label import FoodLedgerQrLabelService
from tests.services.food.helpers import ledger_rows, pages


SYNCED_BY = "batch:sync_data_go_kr_ledgers"


def _service(session) -> FoodLedgerQrLabelService:
    return FoodLedgerQrLabelService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical 식품표시정보 record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "label_no": "202410221000001856",
        "food_label_serial": "1000000001259",
        "product_name": "전복삼계죽 420g",
        "barcode_no": "08801007901244",
        "version_no": "1",
        "valid_from": "20241101",
        "valid_to": "99991231",
        "food_division_name": "가공식품",
        "food_type_name": "즉석조리식품",
        "history_tracked_yn": "N",
        "irradiated_yn": "N",
        "gmo_yn": "N",
        "infant_sale_marked_yn": "N",
        "high_calorie_low_nutrition_yn": "N",
        "pasteurized_yn": "N",
        "sterilized_yn": "N",
        "refrigerated_yn": "N",
        "content_amount_text": "420g (215kcal)",
        "shelf_life_text": "상부 표기일까지",
        "intake_method_text": "",
        "functional_info_text": "",
        "source_updated_at": "2026-07-30",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_ledger_qr_label_after_a_second_pass_is_the_second_pass(factory, pinned) -> None:
    """A re-sent row is written again, under the id its key mints."""
    async with pinned() as session:
        assert await _service(session).replace_qr_label_ledger(pages([_record()]), SYNCED_BY) == (
            1,
            1,
        )

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerQrLabel)

    async with pinned() as session:
        assert await _service(session).replace_qr_label_ledger(pages([_record()]), SYNCED_BY) == (
            1,
            1,
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerQrLabel)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_ledger_qr_label_skips_records_without_a_key(factory, pinned) -> None:
    """A record missing its key cannot be matched again, so it must not be stored."""
    async with pinned() as session:
        assert await _service(session).replace_qr_label_ledger(
            pages(
                [
                    _record(),
                    _record(label_no="   "),
                    _record(label_no=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerQrLabel)) == 1


@pytest.mark.asyncio
async def test_ledger_qr_label_keeps_a_record_with_an_unreadable_timestamp(factory, pinned) -> None:
    """An unparseable 최종수정일시 costs that column, never the record."""
    async with pinned() as session:
        await _service(session).replace_qr_label_ledger(
            pages([_record(source_updated_at="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerQrLabel)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
        assert rows[0].label_no == _record()["label_no"]
