"""FoodLedgerAdminDispositionService tests - the 행정처분 ledger the mfds batch replaces."""

import pytest

from app.models.food.ledger_admin_disposition import FoodLedgerAdminDisposition
from app.services.food.ledger_admin_disposition import FoodLedgerAdminDispositionService
from tests.services.food.helpers import ledger_rows, pages


SYNCED_BY = "batch:sync_food_ledger_admin_disposition"


def _record(**overrides: object) -> dict[str, object]:
    """One canonical record, in the keys the operation's fields map to.

    Copied from a measured row (2026-09-18, window 1/2): a HACCP obligation
    missed, 영업정지 7일, with the two columns this portal never fills left
    empty.
    """
    record: dict[str, object] = {
        "disposition_seq": "4739906",
        "license_no": "20140506502",
        "business_name": "(주)자연의 명가",
        "industry_name": "식품제조가공업",
        "decided_on": "20260918",
        "began_on": "20260921",
        "ended_on": "20260927",
        "disposition_type": "영업정지",
        "violation_text": (
            "(20260825)식품안전관리인증기준(HACCP) 의무적용 품목 미인증\n해당 품목 : 양념젓갈"
        ),
        "disposition_text": "영업정지",
        "law_text": "식품위생법 제48조(식품안전관리인증기준) 2항",
        "address": "전남광주통합특별시 여수시",
        "telephone": "",
        "president_name": "",
        "institution_name": "전남광주통합특별시 여수시",
        "public_until": "2026-10-03 00:00:00.0",
        "source_updated_text": "2026-09-18 01:40:19.181",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_disposition_after_a_second_pass_is_the_second_pass(factory, pinned) -> None:
    """A re-sent row is written again, under the id its 행정처분전산키 mints."""
    async with pinned() as session:
        assert await FoodLedgerAdminDispositionService(session).replace_admin_disposition_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerAdminDisposition)
        assert first.disposition_type == "영업정지"
        assert first.license_no == "20140506502"

    async with pinned() as session:
        assert await FoodLedgerAdminDispositionService(session).replace_admin_disposition_ledger(
            pages([_record(disposition_type="영업허가·등록취소", ended_on="-")]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerAdminDisposition)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].disposition_type == "영업허가·등록취소"
        assert rows[0].ended_on == "-"
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_disposition_keeps_a_row_whose_business_number_is_absent(factory, pinned) -> None:
    """The key is the 전산키 alone, so a row with no 인허가번호 is still a record.

    What it cannot do is join to a product: `license_no` is the only column that
    reaches `food_item_report`, and a disposition without one is a published
    fact about a business nothing in this database can name.
    """
    async with pinned() as session:
        assert await FoodLedgerAdminDispositionService(session).replace_admin_disposition_ledger(
            pages([_record(), _record(disposition_seq="4740799", license_no=None)]), SYNCED_BY
        ) == (2, 2)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerAdminDisposition)
        assert sorted(row.license_no or "" for row in rows) == ["", "20140506502"]


@pytest.mark.asyncio
async def test_disposition_skips_records_without_a_key(factory, pinned) -> None:
    """A record missing its 전산키 cannot be matched again, so it must not be stored."""
    async with pinned() as session:
        assert await FoodLedgerAdminDispositionService(session).replace_admin_disposition_ledger(
            pages([_record(), _record(disposition_seq=None), "not-a-record"]), SYNCED_BY
        ) == (3, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerAdminDisposition)) == 1
