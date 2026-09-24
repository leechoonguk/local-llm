"""FoodLedgerQrNutritionService tests - the ledger the 푸드QR feed replaces every night."""

import pytest

from app.models.food.ledger_qr_nutrition import FoodLedgerQrNutrition
from app.services.food.ledger_qr_nutrition import FoodLedgerQrNutritionService
from tests.services.food.helpers import ledger_rows, pages


SYNCED_BY = "batch:sync_data_go_kr_ledgers"


def _service(session) -> FoodLedgerQrNutritionService:
    return FoodLedgerQrNutritionService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical 영양표시정보 record - the 열량 line of a 420 g 전복삼계죽."""
    record: dict[str, object] = {
        "label_no": "202410221000001856",
        "item_report_serial": "1000000001855",
        "item_report_no": "20190450208110",
        "nutrition_label_serial": "1000000001060",
        "nutrition_detail_serial": "462",
        "barcode_no": "08801007901244",
        "product_name": "전복삼계죽 420g",
        "business_name": "씨제이제일제당(주) 진천 BLOSSOM CAMPUS 3동",
        "version_no": "1",
        "valid_from": "20241101",
        "valid_to": "99991231",
        "basis_name": "총 내용량당",
        "total_content_amount": "420.000",
        "total_content_unit": "g",
        "unit_content_amount": "0.000",
        "unit_content_unit": "",
        "remark_text": (
            "1일 영양성분 기준치에 대한 비율(%)은 2,000kcal 기준이므로 "
            "개인의 필요 열량에 따라 다를 수 있습니다."
        ),
        "format_name": "기본형",
        "label_group_name": "전복삼계죽 420g",
        "unit_content_label_name": "",
        "unit_content_label_amount_name": "",
        "total_piece_label_name": "",
        "nutrient_kind_name": "필수영양성분",
        "nutrient_name": "열량",
        "nutrient_sequence": "1",
        "amount": "215.000",
        "amount_unit": "kcal",
        "amount_unit_etc": "",
        "daily_value_pct": "",
        "additional_item_division_yn": "",
        "additional_item_division_name": "",
        "additional_item_1_name": "",
        "additional_item_2_name": "",
        "additional_item_3_name": "",
        "additional_item_4_name": "",
        "additional_item_5_name": "",
        "additional_item_1_amount": "",
        "additional_item_2_amount": "",
        "additional_item_3_amount": "",
        "additional_item_4_amount": "",
        "additional_item_5_amount": "",
        "additional_item_1_ratio": "",
        "additional_item_2_ratio": "",
        "additional_item_3_ratio": "",
        "additional_item_4_ratio": "",
        "additional_item_5_ratio": "",
        "additional_item_1_unit_etc": "",
        "additional_item_2_unit_etc": "",
        "additional_item_3_unit_etc": "",
        "additional_item_4_unit_etc": "",
        "additional_item_5_unit_etc": "",
        "intake_basis_name": "",
        "intake_amount": "",
        "intake_amount_unit": "",
        "intake_weight": "",
        "intake_weight_unit": "",
        "source_updated_at": "2026-07-30 19:03:34",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_ledger_qr_nutrition_after_a_second_pass_is_the_second_pass(factory, pinned) -> None:
    """A re-sent row is written again, under the id its key mints."""
    async with pinned() as session:
        assert await _service(session).replace_qr_nutrition_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerQrNutrition)

    async with pinned() as session:
        assert await _service(session).replace_qr_nutrition_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerQrNutrition)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_ledger_qr_nutrition_skips_records_without_a_key(factory, pinned) -> None:
    """A record missing its key cannot be matched again, so it must not be stored."""
    async with pinned() as session:
        assert await _service(session).replace_qr_nutrition_ledger(
            pages(
                [
                    _record(),
                    _record(label_no="   "),
                    _record(nutrition_detail_serial=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerQrNutrition)) == 1


@pytest.mark.asyncio
async def test_ledger_qr_nutrition_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 최종수정일시 costs that column, never the record."""
    async with pinned() as session:
        await _service(session).replace_qr_nutrition_ledger(
            pages([_record(source_updated_at="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerQrNutrition)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
        assert rows[0].item_report_no == _record()["item_report_no"]
