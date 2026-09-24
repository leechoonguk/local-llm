"""FoodLedgerRecallService tests - the 회수·판매중지 ledger the mfds batch replaces."""

import pytest

from app.models.food.ledger_recall import FoodLedgerRecall
from app.services.food.ledger_recall import FoodLedgerRecallService
from tests.services.food.helpers import ledger_rows, pages


SYNCED_BY = "batch:sync_mfds_ledgers"


def _record(**overrides: object) -> dict[str, object]:
    """One canonical record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "recall_disuse_seq": "3000234541",
        "item_report_no": "200900200209",
        "license_no": "20090020020",
        "product_name": "청인 해우",
        "business_name": "(주)힐링바이오",
        "address": "충청북도 청주시 서원구",
        "telephone": "",
        "barcode_no": "",
        "packaging_unit": "",
        "manufactured_text": "데이터없음",
        "recall_reason": "정부수거검사 부적합(프로바이오틱스 수)",
        "recall_method": "",
        "recall_grade": "3등급",
        "shelf_life_text": "제조일로부터 24개월",
        "product_type_group": "건강기능식품",
        "product_code": "E0205100000000",
        "product_type_name": "프로바이오틱스",
        "image_url": "http://coop.foodsafetykorea.go.kr/open/minfo_image.jpg",
        "registered_at": "2026-09-14 17:19:13.501282",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_recall_after_a_second_pass_is_the_second_pass(factory, pinned) -> None:
    """A re-sent row is written again, under the id its serial mints."""
    async with pinned() as session:
        assert await FoodLedgerRecallService(session).replace_recall_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerRecall)
        assert first.recall_reason == "정부수거검사 부적합(프로바이오틱스 수)"
        assert first.registered_at is not None

    async with pinned() as session:
        assert await FoodLedgerRecallService(session).replace_recall_ledger(
            pages([_record(recall_grade="2등급")]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerRecall)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].recall_grade == "2등급"
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_recall_keeps_a_row_whose_product_number_is_absent(factory, pinned) -> None:
    """192 of 376 rows carry a 품목제조보고번호 (2026-09-14); the rest are still records.

    Only the serial is the key, so a 농·수산물 recall with no 품목제조보고 is
    stored like any other - what it cannot do is join to a product.
    """
    async with pinned() as session:
        assert await FoodLedgerRecallService(session).replace_recall_ledger(
            pages([_record(), _record(recall_disuse_seq="3000234542", item_report_no=None)]),
            SYNCED_BY,
        ) == (2, 2)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerRecall)
        assert sorted(row.item_report_no or "" for row in rows) == ["", "200900200209"]


@pytest.mark.asyncio
async def test_recall_skips_records_without_a_key(factory, pinned) -> None:
    """A record missing its serial cannot be matched again, so it must not be stored."""
    async with pinned() as session:
        assert await FoodLedgerRecallService(session).replace_recall_ledger(
            pages([_record(), _record(recall_disuse_seq=None), "not-a-record"]),
            SYNCED_BY,
        ) == (3, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerRecall)) == 1
