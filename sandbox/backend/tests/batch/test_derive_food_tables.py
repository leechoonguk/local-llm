"""Batch job tests — derive_food_tables against an in-memory engine."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.batch.derive_food_tables as derive
from app.core.exceptions import BatchSkippedError
from app.models.food.item_report import FoodItemReport
from app.models.food.item_report_declaration import FoodItemReportDeclaration
from app.models.food.item_report_ingredient import FoodItemReportIngredient
from app.models.food.label import FoodLabel
from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from app.models.food.ledger_inspection_failure import FoodLedgerInspectionFailure
from app.models.food.ledger_item_report import FoodLedgerItemReport
from app.models.food.ledger_item_report_raw_material import FoodLedgerItemReportRawMaterial
from app.models.food.ledger_nutrition import FoodLedgerNutrition
from app.models.food.ledger_product_classification import FoodLedgerProductClassification
from app.models.food.ledger_raw_material import FoodLedgerRawMaterial
from app.models.food.ledger_recall import FoodLedgerRecall
from app.models.food.nutrition import FoodNutrition
from app.models.food.product_classification import FoodProductClassification
from app.models.food.raw_material import FoodRawMaterial
from app.models.food.safety_record import FoodSafetyRecord
from app.services.batch.run import BatchRunService, current_run_id
from tests.batch.scripted import rows, swapped_engine


async def _ledgers(engine) -> None:
    """One row in each ledger the derivations read - enough to see each table filled."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerProductClassification(
                    product_code="C0301040000000",
                    korean_name="빵류",
                    product_yn="Y",
                    valid_end_date="99991231",
                ),
                FoodLedgerRawMaterial(
                    raw_material_code="A1000911010001", representative_raw_material_name="밀가루"
                ),
                FoodLedgerItemReport(item_report_no="1", product_type_name="빵류"),
                FoodLedgerItemReportRawMaterial(
                    item_report_no="1",
                    raw_material_names="밀가루, 정제수",
                    raw_material_ordinals="1,2",
                ),
                FoodLedgerNutrition(
                    food_code="D101-004160000-0001", food_name="찐빵", item_report_no="1"
                ),
                # One 회수 and one 부적합, so the event derivation runs too: the
                # recall names a reported product, the inspection names none.
                FoodLedgerRecall(
                    recall_disuse_seq="3000234541",
                    item_report_no="1",
                    product_name="찐빵",
                    recall_reason="정부수거검사 부적합",
                    registered_at=datetime(2026, 9, 14, 17, 19, 13, tzinfo=UTC),
                ),
                FoodLedgerInspectionFailure(
                    disposal_seq="3000222960",
                    test_item_name="프로사이미돈",
                    standard_text="5.0 mg/kg 이하",
                    test_result_text="20.2 mg/kg",
                    product_name="부추(L23)",
                    registered_on="2026.03.11",
                ),
                # One 수입신고, so the job's import half runs too: the product,
                # the declaration, the printed label and its three children,
                # and the ingredients read out of that label.
                FoodLedgerImportFoodLabel(
                    importer_name="쏠트코리아",
                    product_name="천일염",
                    product_name_en="SEA SALT",
                    product_type_name="천일염",
                    overseas_maker_name="UBAIDIA",
                    origin_country="파키스탄",
                    export_country="파키스탄",
                    processed_date="20260911",
                    expiry_text="20180810 ~ 20280809",
                    expiry_from="20180810",
                    expiry_to="20280809",
                    declaration_kind="가공식품",
                    label_text=(
                        "원재료명 : 천일염 "
                        "포장재질 : 폴리에틸렌 "
                        "주의사항 : 직사광선을 피해 보관 "
                        "천일염 함유"
                    ),
                ),
            ]
        )
        await session.commit()


async def _start_run(engine, code: str) -> UUID:
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        run = await BatchRunService(session).create_started_run(None, code, "CRON", "scheduler")
        return run.id


@pytest.mark.asyncio
async def test_derive_rebuilds_every_table_off_the_ledgers() -> None:
    """One run fills every derived table, and reports the rows it wrote over all of them."""
    async with swapped_engine(derive) as engine:
        await _ledgers(engine)

        # classification 1 + material 1 + reports 2 + ingredients 3 + events 2 +
        # nutrition 1 + declaration 1 + label 1 + allergen 1 + caution 1 +
        # packaging 1 = 15 rows over eleven tables, every half of the job.
        assert await derive.derive_food_tables() == 1 + 1 + 2 + 3 + 2 + 1 + 1 + 1 + 1 + 1 + 1

        assert [r.product_code for r in await rows(engine, FoodProductClassification)] == [
            "C0301040000000"
        ]
        assert [r.base_code for r in await rows(engine, FoodRawMaterial)] == ["A1000911"]
        reports = await rows(engine, FoodItemReport)
        assert sorted(r.report_kind for r in reports) == ["domestic", "import"]
        imported = next(r for r in reports if r.report_kind == "import")
        assert (imported.maker_name, imported.origin_country, imported.report_date) == (
            "UBAIDIA",
            "파키스탄",
            "20260911",
        )
        assert [r.export_country for r in await rows(engine, FoodItemReportDeclaration)] == [
            "파키스탄"
        ]
        assert [r.source for r in await rows(engine, FoodLabel)] == ["import"]
        events = await rows(engine, FoodSafetyRecord)
        assert sorted((e.record_kind, e.report_kind, e.recorded_on) for e in events) == [
            ("inspection_failure", None, "20260311"),
            ("recall", "domestic", "20260914"),
        ]
        assert sorted(r.name for r in await rows(engine, FoodItemReportIngredient)) == [
            "밀가루",
            "정제수",
            "천일염",
        ]
        assert [(r.food_code, r.item_report_no) for r in await rows(engine, FoodNutrition)] == [
            ("D101-004160000-0001", "1")
        ]


@pytest.mark.asyncio
async def test_derive_stands_down_while_a_ledger_job_is_running() -> None:
    """A ledger job in flight means the ledgers are about to change: skip, write nothing.

    The job says so by raising, and the scheduler records the run SKIPPED with
    the reason - the ledgers this repository reads are walked over three
    nights, so a daily fire meets one mid-walk often enough that "nothing
    happened" has to be distinguishable from "nothing was wrong".

    Any other job running is not its business - only the ones whose ledgers it
    reads, and a second derivation, which would write the same fifteen tables.
    Its own run - the row the scheduler opened for this very execution - is
    what `current_run_id` names, and is not somebody else.
    """
    async with swapped_engine(derive) as engine:
        await _ledgers(engine)
        await _start_run(engine, "sync_food_ledger_item_report")

        with pytest.raises(BatchSkippedError, match="sync_food_ledger_item_report"):
            await derive.derive_food_tables()
        assert await rows(engine, FoodItemReport) == []

    async with swapped_engine(derive) as engine:
        await _ledgers(engine)
        await _start_run(engine, "derive_food_tables")

        with pytest.raises(BatchSkippedError, match="derive_food_tables"):
            await derive.derive_food_tables()
        assert await rows(engine, FoodItemReport) == []

    async with swapped_engine(derive) as engine:
        await _ledgers(engine)
        await _start_run(engine, "purge_old_batch_runs")
        own = await _start_run(engine, "derive_food_tables")

        token = current_run_id.set(own)
        try:
            assert await derive.derive_food_tables() == 15
        finally:
            current_run_id.reset(token)
