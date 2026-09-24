"""FoodLedgerImportFoodLabelService tests - the ledger the data.go.kr batch replaces."""

import pytest

from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from app.services.food.ledger_import_food_label import FoodLedgerImportFoodLabelService
from tests.services.food.helpers import ledger_rows, pages


SYNCED_BY = "batch:sync_data_go_kr_ledgers"


def _service(session) -> FoodLedgerImportFoodLabelService:
    return FoodLedgerImportFoodLabelService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical record, in the keys the operation's fields map to (measured 2026-09-13)."""
    record: dict[str, object] = {
        "importer_name": "주식회사 쏠트코리아",
        "product_name": "천일염(식용)",
        "product_name_en": "SEA SALT",
        "declaration_kind": "가공식품",
        "product_type_name": "천일염",
        "overseas_maker_name": "UBAIDIA MINERALS",
        "origin_country": "파키스탄",
        "export_country": "파키스탄",
        "processed_date": "20200508",
        "expiry_text": "20180810 ~ 20280809",
        "expiry_from": "20180810",
        "expiry_to": "20280809",
        "label_text": "식품위생법에 의한 한글표시사항\n염의종류 : 천일염\n중량 : 1250KG",
        "raw_material_names": None,
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_import_food_label_after_a_second_pass_is_the_second_pass(factory, pinned) -> None:
    """A re-sent record keeps its id: the key is the nine columns, not the night."""
    async with pinned() as session:
        assert await _service(session).replace_import_food_label_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerImportFoodLabel)
        label = "식품위생법에 의한 한글표시사항\n염의종류 : 천일염\n중량 : 1250KG"
        assert first.label_text == label

    async with pinned() as session:
        assert await _service(session).replace_import_food_label_ledger(
            pages([_record(label_text="바뀐 표시사항")]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerImportFoodLabel)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].label_text == "바뀐 표시사항"


@pytest.mark.asyncio
async def test_import_food_label_separates_records_the_publisher_left_alike(
    factory, pinned
) -> None:
    """Two declarations of one product differ only in the columns the key carries.

    Measured over the whole feed: 수입업체+제품명+처리일자+유통기한 alone leave
    1,017,499 distinct of 1,087,781, so the key is every answered column but the
    two texts - and a record with no 수입업체 at all is skipped, because no later
    pass could match it.
    """
    async with pinned() as session:
        assert await _service(session).replace_import_food_label_ledger(
            pages(
                [
                    _record(),
                    _record(processed_date="20260911"),
                    _record(overseas_maker_name="OTHER MINERALS"),
                    _record(importer_name=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (5, 3)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerImportFoodLabel)) == 3
