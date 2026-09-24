"""FoodLedgerHealthFunctionalItemReportService tests - the 건강기능식품 ledger."""

import pytest

from app.models.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReport,
)
from app.services.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReportService,
)
from tests.services.food.helpers import ledger_rows, pages


SYNCED_BY = "batch:sync_mfds_ledgers"


def _record(**overrides: object) -> dict[str, object]:
    """One canonical record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "item_report_no": "20140017002183",
        "product_name": "11종 혼합유산균",
        "business_name": "일동바이오사이언스(주)",
        "license_no": "20140017002",
        "permit_date": "20201027",
        "product_type_name": "프로바이오틱스",
        "product_shape": "분말",
        "product_form": "고유의 향미가 있고 이미·이취가 없는 분말",
        "intake_method": "건강기능식품 원료로 사용",
        "primary_functionality": "유산균 증식 및 유해균 억제에 도움을 줄 수 있음",
        "intake_caution": "1. 질환이 있거나 의약품 복용 시 전문가와 상담하십시오.",
        "storage_method": "",
        "standard_spec": "1. 성상 : 노랑 하양색의 분말",
        "shelf_life": "제조일로부터 24개월까지",
        "packaging_material": "내피:PE, 외피:알미늄Pack",
        "packaging_method": "PE 재질의 포장지로 이중 포장한다.",
        "functional_indicator": "프로바이오틱스",
        "functional_raw_material_names": (
            "Lactobacillus acidophilus(고시형), Bifidobacterium breve(고시형)"
        ),
        "other_raw_material_names": "",
        "capsule_raw_material_names": "",
        "high_calorie_low_nutrition": "해당없음",
        "production_ended": "아니오",
        "child_favorite_certified_yn": "",
        "industry_name": "건강기능식품전문제조업",
        "source_updated_at": "20260721",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_health_functional_after_a_second_pass_is_the_second_pass(factory, pinned) -> None:
    """A re-sent row is written again, under the id its 품목제조번호 mints."""
    service = FoodLedgerHealthFunctionalItemReportService
    async with pinned() as session:
        assert await service(session).replace_health_functional_item_report_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerHealthFunctionalItemReport)
        # The three 원재료 lists stay the publisher's strings; the split is the
        # derivation's (rule://backend-ledger).
        assert first.functional_raw_material_names is not None
        assert first.storage_method is None

    async with pinned() as session:
        assert await service(session).replace_health_functional_item_report_ledger(
            pages([_record(production_ended="예")]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerHealthFunctionalItemReport)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].production_ended == "예"
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_health_functional_skips_records_without_a_key(factory, pinned) -> None:
    """A record missing its 품목제조번호 cannot be matched again, so it must not be stored."""
    service = FoodLedgerHealthFunctionalItemReportService
    async with pinned() as session:
        assert await service(session).replace_health_functional_item_report_ledger(
            pages([_record(), _record(item_report_no=None), "not-a-record"]), SYNCED_BY
        ) == (3, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerHealthFunctionalItemReport)) == 1
