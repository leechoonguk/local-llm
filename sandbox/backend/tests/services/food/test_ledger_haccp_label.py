"""FoodLedgerHaccpLabelService tests - the ledger the data.go.kr batch replaces."""

import pytest

from app.models.food.ledger_haccp_label import FoodLedgerHaccpLabel
from app.services.food.ledger_haccp_label import FoodLedgerHaccpLabelService
from tests.services.food.helpers import ledger_rows, pages


SYNCED_BY = "batch:sync_data_go_kr_ledgers"


def _service(session) -> FoodLedgerHaccpLabelService:
    return FoodLedgerHaccpLabelService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "item_report_no": "201904962715",
        "product_kind_division": "식품",
        "product_name": "설화눈꽃팝김부각스낵",
        "raw_material_names": (
            "찹쌀,김,참깨,옥수수기름(옥배유),양파,무,대파,천일염,"
            "마늘,새우,멸치,다시마,건표고버섯,둥굴레,감초,정제수"
        ),
        "allergy_names": "없음",
        "product_type_name": "과자",
        "product_type_state": "낱개 및 세트박스 포장",
        "maker_name": "남원혼불부각",
        "seller_name": "",
        "capacity_text": "",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_haccp_label_after_a_second_pass_is_the_second_pass(factory, pinned) -> None:
    """A re-sent row is written again, under the id its key mints."""
    async with pinned() as session:
        assert await _service(session).replace_haccp_label_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerHaccpLabel)

    async with pinned() as session:
        assert await _service(session).replace_haccp_label_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerHaccpLabel)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_haccp_label_skips_records_without_a_key(factory, pinned) -> None:
    """A record missing its key cannot be matched again, so it must not be stored."""
    async with pinned() as session:
        assert await _service(session).replace_haccp_label_ledger(
            pages(
                [
                    _record(),
                    _record(item_report_no=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (3, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerHaccpLabel)) == 1
