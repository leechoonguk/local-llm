"""FoodSafetyRecordService tests - the events read off the two supervising feeds."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models.food.item_report import FoodItemReport
from app.models.food.ledger_collection_inspection import FoodLedgerCollectionInspection
from app.models.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReport,
)
from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from app.models.food.ledger_inspection_failure import FoodLedgerInspectionFailure
from app.models.food.ledger_item_report import FoodLedgerItemReport
from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial,
)
from app.models.food.ledger_recall import FoodLedgerRecall
from app.models.food.safety_record import FoodSafetyRecord
from app.schemas.food.item_report import FoodSafetyRecordFilter
from app.services.food.safety_record import FoodSafetyRecordService


SYNCED_BY = "batch:derive_food_tables"


async def _ledgers(factory) -> None:
    """Two reported products, a recall, two failed test items and two collected specimens."""
    async with factory() as session, session.begin():
        session.add_all(
            [
                FoodLedgerItemReport(item_report_no="20130368349343", product_name="찐빵"),
                FoodLedgerLivestockItemReportRawMaterial(
                    item_report_no="L1", raw_material_names="돼지고기"
                ),
                FoodLedgerRecall(
                    recall_disuse_seq="3000234541",
                    item_report_no="20130368349343",
                    product_name="청인 해우",
                    business_name="(주)힐링바이오",
                    product_type_name="프로바이오틱스",
                    recall_reason="정부수거검사 부적합",
                    recall_grade="3등급",
                    registered_at=datetime(2026, 9, 14, 17, 19, 13, tzinfo=UTC),
                    created_by="test",
                    updated_by="test",
                ),
                # A recall of something no registry reported: 농·수산물, half the feed.
                FoodLedgerRecall(
                    recall_disuse_seq="3000234542",
                    item_report_no=None,
                    product_name="자연산 미역",
                    recall_reason="이물 혼입",
                    registered_at=datetime(2026, 9, 13, 10, 0, tzinfo=UTC),
                    created_by="test",
                    updated_by="test",
                ),
                FoodLedgerInspectionFailure(
                    disposal_seq="3000222960",
                    test_item_name="프로사이미돈",
                    standard_text="5.0 mg/kg 이하",
                    test_result_text="20.2 mg/kg",
                    institution_name="울산광역시 보건환경연구원",
                    item_report_no="L1",
                    product_name="부추(L23)",
                    registered_on="2026.03.11",
                    created_by="test",
                    updated_by="test",
                ),
                FoodLedgerInspectionFailure(
                    disposal_seq="3000222960",
                    test_item_name="플루디옥소닐",
                    standard_text="5.0 mg/kg 이하",
                    test_result_text="6.22 mg/kg",
                    item_report_no="L1",
                    product_name="부추(L23)",
                    registered_on="2026.03.11",
                    created_by="test",
                    updated_by="test",
                ),
                # 수거검사: both verdicts are records. 68.3 % of that feed reads
                # 적합, and those rows are what tell "never sampled" from
                # "sampled and clean" - the distinction the table exists for.
                FoodLedgerCollectionInspection(
                    record_digest="c" * 64,
                    item_report_no="20130368349343",
                    product_name="연돈카레",
                    business_name="에프와이지주식회사 괴산공장지점",
                    collected_on="20260825",
                    judgment="부적합",
                    institution_name="충청북도 괴산군",
                    plan_title="민원관련 수거검사",
                    created_by="test",
                    updated_by="test",
                ),
                # 건강기능식품 is a registry of its own (I0030): left out of the
                # lookup, every 수거검사 of one carried its number with no kind
                # and the read layer dropped it - 18,536 records, 5,648 numbers.
                FoodLedgerHealthFunctionalItemReport(
                    item_report_no="H1",
                    product_name="프로바이오틱스",
                    created_by="test",
                    updated_by="test",
                ),
                FoodLedgerCollectionInspection(
                    record_digest="f" * 64,
                    item_report_no="H1",
                    product_name="프로바이오틱스",
                    collected_on="20260901",
                    judgment="적합",
                    created_by="test",
                    updated_by="test",
                ),
                FoodLedgerCollectionInspection(
                    record_digest="d" * 64,
                    item_report_no="20130368349343",
                    product_name="연돈카레",
                    collected_on="20260910",
                    judgment="적합",
                    created_by="test",
                    updated_by="test",
                ),
            ]
        )


@pytest.mark.asyncio
async def test_every_published_record_is_a_row_under_its_own_key(factory, pinned) -> None:
    """Three feeds land in one table, each row keyed by the digest of its own feed's key.

    One disposal with two failed items is two records, because the item is what
    the inspection found - which is the same reason the ledger keys on it.
    """
    await _ledgers(factory)

    async with pinned() as session:
        assert await FoodSafetyRecordService(session).rebuild_safety_record(SYNCED_BY) == 7

    async with factory() as session:
        listed = await session.execute(
            select(FoodSafetyRecord).order_by(FoodSafetyRecord.record_key)
        )
        rows = listed.scalars().all()
        assert sorted(row.record_kind for row in rows) == [
            "collection_inspection",
            "collection_inspection",
            "collection_inspection",
            "inspection_failure",
            "inspection_failure",
            "recall",
            "recall",
        ]
        assert len({row.record_key for row in rows}) == 7
        assert {row.record_key[0] for row in rows} == {"R", "F", "C"}


@pytest.mark.asyncio
async def test_the_portals_html_entities_do_not_reach_a_screen(factory, pinned) -> None:
    """The feed escapes for a web page; a table is not one.

    Measured over the whole record set: 27,160 reasons carry an entity
    (`&#39;` 16,468, `&middot;` 8,988, `&rsquo;` 1,331), so a plan title read
    straight off the ledger printed `2026년 국내 주류 수거&middot;검사`.
    """
    async with factory() as session, session.begin():
        session.add(
            FoodLedgerCollectionInspection(
                record_digest="e" * 64,
                item_report_no="20130368349343",
                product_name="이슬톡톡 &#39;복숭아&#39;",
                collected_on="20260917",
                judgment="적합",
                plan_title="2026년 국내 주류 수거&middot;검사",
                created_by="test",
                updated_by="test",
            )
        )

    async with pinned() as session:
        await FoodSafetyRecordService(session).rebuild_safety_record(SYNCED_BY)

    async with factory() as session:
        listed = await session.execute(
            select(FoodSafetyRecord).where(FoodSafetyRecord.recorded_on == "20260917")
        )
        (row,) = listed.scalars().all()
        assert row.reason == "2026년 국내 주류 수거·검사"
        assert row.product_name == "이슬톡톡 '복숭아'"


@pytest.mark.asyncio
async def test_a_clean_inspection_is_a_record_too(factory, pinned) -> None:
    """수거검사 lands whatever it was judged - the 적합 beside the 부적합.

    Keeping only the failures made a product never sampled and a product
    sampled and clean read the same: "nothing published". 84,129 of our
    products carry an inspection and 1,867 numbers carry a failure, so the
    verdict is the column that tells them apart. The feed publishes no 검사항목
    and no measurement, so the plan it was collected under is what the row says.
    """
    await _ledgers(factory)

    async with pinned() as session:
        await FoodSafetyRecordService(session).rebuild_safety_record(SYNCED_BY)

    async with factory() as session:
        listed = await session.execute(
            select(FoodSafetyRecord)
            .where(FoodSafetyRecord.record_kind == "collection_inspection")
            .where(FoodSafetyRecord.item_report_no == "20130368349343")
            .order_by(FoodSafetyRecord.recorded_on)
        )
        failed, clean = listed.scalars().all()
        assert (failed.judgment, failed.recorded_on) == ("부적합", "20260825")
        assert failed.product_name == "연돈카레"
        assert failed.reason == "민원관련 수거검사"
        assert failed.institution_name == "충청북도 괴산군"
        assert failed.report_kind == "domestic"
        assert failed.test_item_name is None
        assert (clean.judgment, clean.recorded_on) == ("적합", "20260910")


@pytest.mark.asyncio
async def test_the_kind_is_the_registry_the_number_is_in(factory, pinned) -> None:
    """A number in I1250 is domestic, one in C006 livestock, one in neither has no kind.

    Measured 2026-09-14: 147 of 174 회수 numbers and 57 of 70 부적합 numbers are
    in a registry; the rest are 농·수·축산물 and imports nobody reports.
    """
    await _ledgers(factory)

    async with pinned() as session:
        await FoodSafetyRecordService(session).rebuild_safety_record(SYNCED_BY)

    async with factory() as session:
        rows = (await session.execute(select(FoodSafetyRecord))).scalars().all()
        by_product = {(row.item_report_no, row.record_kind): row.report_kind for row in rows}
        assert by_product[("20130368349343", "recall")] == "domestic"
        assert by_product[("L1", "inspection_failure")] == "livestock"
        assert by_product[("H1", "collection_inspection")] == "health_functional"
        assert by_product[(None, "recall")] is None


@pytest.mark.asyncio
async def test_each_feeds_date_is_read_out_of_its_own_spelling(factory, pinned) -> None:
    """I0490 stamps a timestamp, I2620 dots a date; the table holds one day either way."""
    await _ledgers(factory)

    async with pinned() as session:
        await FoodSafetyRecordService(session).rebuild_safety_record(SYNCED_BY)

    async with factory() as session:
        rows = (await session.execute(select(FoodSafetyRecord))).scalars().all()
        dates = {
            row.record_kind: {r.recorded_on for r in rows if r.record_kind == row.record_kind}
            for row in rows
        }
        assert dates["recall"] == {"20260914", "20260913"}
        assert dates["inspection_failure"] == {"20260311"}


@pytest.mark.asyncio
async def test_a_rebuild_replaces_and_keeps_every_key(factory, pinned) -> None:
    """The table is dropped and refilled nightly; a key is a function of the record."""
    await _ledgers(factory)

    async with pinned() as session:
        await FoodSafetyRecordService(session).rebuild_safety_record(SYNCED_BY)
    async with factory() as session:
        listed = await session.execute(select(FoodSafetyRecord))
        before = {row.record_key: row.id for row in listed.scalars().all()}

    async with pinned() as session:
        assert await FoodSafetyRecordService(session).rebuild_safety_record(SYNCED_BY) == 7
    async with factory() as session:
        listed = await session.execute(select(FoodSafetyRecord))
        after = {row.record_key: row.id for row in listed.scalars().all()}

    assert after == before


@pytest.mark.asyncio
async def test_an_event_reaches_the_product_its_number_names(factory, pinned) -> None:
    """The edge a screen reads: the recall of a reported product resolves to that row."""
    await _ledgers(factory)
    async with factory() as session, session.begin():
        session.add(
            FoodItemReport(
                report_kind="domestic",
                item_report_no="20130368349343",
                product_name="찐빵",
                created_by="test",
                updated_by="test",
            )
        )

    async with pinned() as session:
        await FoodSafetyRecordService(session).rebuild_safety_record(SYNCED_BY)

    async with factory() as session:
        event = (
            await session.execute(
                select(FoodSafetyRecord)
                .where(FoodSafetyRecord.record_kind == "recall")
                .where(FoodSafetyRecord.item_report_no == "20130368349343")
            )
        ).scalar_one()
        report = (
            await session.execute(
                select(FoodItemReport).where(
                    FoodItemReport.report_kind == event.report_kind,
                    FoodItemReport.item_report_no == event.item_report_no,
                )
            )
        ).scalar_one()
        assert report.product_name == "찐빵"


@pytest.mark.asyncio
async def test_a_product_reads_its_events_newest_first(factory, pinned) -> None:
    """The read side: one product's events, in the order a reader wants them.

    A product with none answers 0 and an empty page - which is the usual
    answer, 948 events over 1.9M products (2026-09-14).
    """
    await _ledgers(factory)
    async with pinned() as session:
        await FoodSafetyRecordService(session).rebuild_safety_record(SYNCED_BY)

    async with factory() as session:
        service = FoodSafetyRecordService(session)
        assert await service.count_records("livestock", "L1") == 2
        rows = await service.list_records("livestock", "L1")
        # One day, so the key breaks the tie - stably, which is the point.
        assert [row.test_item_name for row in rows] == ["프로사이미돈", "플루디옥소닐"]
        page = await service.list_records("livestock", "L1", offset=1, limit=1)
        assert [row.test_item_name for row in page] == ["플루디옥소닐"]
        assert await service.count_records("domestic", "L1") == 0
        assert await service.list_records("domestic", "L1") == []


@pytest.mark.asyncio
async def test_events_are_read_as_a_list_of_their_own(factory, pinned) -> None:
    """An event is an authority's action, read by date and kind over every product.

    Newest first, narrowed by what the authority published from - the kind of
    event, the registry, the year - and by the names a reader types.
    """
    await _ledgers(factory)
    async with pinned() as session:
        await FoodSafetyRecordService(session).rebuild_safety_record(SYNCED_BY)

    async with factory() as session:
        service = FoodSafetyRecordService(session)
        page = await service.list_safety_records(0, 10)
        dates = [str(event.recorded_on) for event in page]
        assert dates == sorted(dates, reverse=True)
        assert await service.count_safety_records() == len(page)

        recalls = FoodSafetyRecordFilter(record_kind="recall")
        assert await service.count_safety_records(recalls) == len(
            [event for event in page if event.record_kind == "recall"]
        )
        assert (
            await service.count_safety_records(FoodSafetyRecordFilter(product_name="없는제품")) == 0
        )

        facets = await service.list_safety_record_facets()
        assert set(facets.record_kind) == {event.record_kind for event in page}
        assert facets.record_year == sorted(
            {str(event.recorded_on)[:4] for event in page if event.recorded_on}, reverse=True
        )


@pytest.mark.asyncio
async def test_a_products_summary_counts_every_record_not_one_page(factory, pinned) -> None:
    """The header's numbers are the product's, whatever window the reader is on.

    Counted in the component off the rows in hand, a product whose only failure
    sits on page 1 reads "부적합 0건" on page 2 - the one number the header
    exists for, wrong exactly when it matters.
    """
    await _ledgers(factory)

    async with pinned() as session:
        await FoodSafetyRecordService(session).rebuild_safety_record(SYNCED_BY)

    async with factory() as session:
        service = FoodSafetyRecordService(session)
        records, failed, latest = await service.summarise_records("domestic", "20130368349343")
        first_page = await service.list_records("domestic", "20130368349343", 0, 1)
        assert (records, failed, latest) == (3, 1, "20260914")
        # One row in hand, three counted: the summary is not the page.
        assert len(first_page) == 1
        assert await service.summarise_records("domestic", "없는번호") == (0, 0, None)


def _import_label(**overrides: object) -> FoodLedgerImportFoodLabel:
    # 가공식품, because a product is what the registries can name: the real
    # 목이버섯 recall this shape was measured on is 농.임산물, a crossing of a
    # commodity, and under `PRODUCT_DECLARATION_KINDS` it derives no product
    # and resolves no event - see the last case in the test below.
    values: dict[str, object] = {
        "importer_name": "(주)태양무역",
        "product_name": "목이버섯(1kg*10)",
        "product_name_en": "DRIED BLACK FUNGUS",
        "product_type_name": "목이버섯",
        "overseas_maker_name": "HUBEI PIAOYANG FOOD",
        "origin_country": "중국",
        "export_country": "중국",
        "processed_date": "20260625",
        "expiry_text": "20260526 ~ 20280525",
        "expiry_from": "20260526",
        "expiry_to": "20280525",
        "declaration_kind": "가공식품",
        "created_by": "test",
        "updated_by": "test",
    }
    values.update(overrides)
    return FoodLedgerImportFoodLabel(**values)


def _import_recall(seq: str, **overrides: object) -> FoodLedgerRecall:
    values: dict[str, object] = {
        "recall_disuse_seq": seq,
        "item_report_no": None,
        "product_name": "목이버섯",
        "business_name": "(주)태양무역",
        "manufactured_text": "(포장일자) 2026.5.26",
        "recall_reason": "잔류농약 기준 초과",
        "recall_grade": "2등급",
        "registered_at": datetime(2026, 9, 10, 9, 28, tzinfo=UTC),
        "created_by": "test",
        "updated_by": "test",
    }
    values.update(overrides)
    return FoodLedgerRecall(**values)


@pytest.mark.asyncio
async def test_an_import_event_reaches_the_declaration_it_sat_on(factory, pinned) -> None:
    """An import has no number; the portal hangs its recall on one 수입신고 - the lot.

    (주)태양무역 declared 목이버섯 six times and the 잔류농약 recall sat on the
    one whose 소비기한 starts on the recall's 제조일자 (impfood, 2026-09-20).
    So `(수입업체, 제조일자)` reaches the declaration ledger, the product is the
    digest that ledger's derivation numbers it by, and the lot is kept as a
    day so the declarations tab can say which 신고 it was.
    """
    lot = _import_label()
    other_lot = _import_label(
        processed_date="20260917", expiry_text="20260828 ~ 20280827", expiry_from="20260828"
    )
    # Same importer, same day, another product: the name must pick.
    shrimp = _import_label(
        product_name="냉동흰다리새우살(자숙)", product_name_en="SHRIMP", product_type_name="새우"
    )
    async with factory() as session, session.begin():
        session.add_all(
            [
                lot,
                other_lot,
                shrimp,
                # The recall spells the product without its package: the lot has
                # two products, and the name matches one of them whole.
                _import_recall("4000000001", product_name="냉동흰다리새우살 (자숙)"),
                # The name matches neither product on the lot, so the lot alone
                # cannot say which - unresolved, not guessed.
                _import_recall("4000000002", product_name="목이버섯"),
                # A range names many lots and is read as none.
                _import_recall("4000000003", manufactured_text="(제조일자)2026-05-01~2026-05-31"),
                # A day the importer declared nothing on: no lot, no product.
                _import_recall("4000000006", manufactured_text="(포장일자) 2026.1.1"),
                # A printed number that resolves nowhere is not tried as an
                # import: it named a registry, just not one held.
                _import_recall("4000000004", item_report_no="99999999999999"),
                # A lot that exists but is a crossing of a commodity (농.임산물):
                # no product derives from it, so the event resolves to nothing
                # rather than to a digest no product row carries.
                _import_label(
                    importer_name="청과무역",
                    product_name="브로콜리",
                    product_type_name="브로콜리(신선)",
                    declaration_kind="농.임산물",
                    expiry_from="20260301",
                ),
                _import_recall(
                    "4000000007",
                    business_name="청과무역",
                    product_name="브로콜리",
                    manufactured_text="(포장일자) 2026.3.1",
                ),
            ]
        )
    async with pinned() as session:
        await FoodSafetyRecordService(session).rebuild_safety_record(SYNCED_BY)

    async with factory() as session:
        rows = (await session.execute(select(FoodSafetyRecord))).scalars().all()
        by_seq = {row.record_key: row for row in rows}
        assert len(by_seq) == 6
        resolved = [row for row in rows if row.report_kind == "import"]
        assert [row.product_name for row in resolved] == ["냉동흰다리새우살 (자숙)"]
        assert resolved[0].lot_date == "20260526"
        assert str(resolved[0].item_report_no).startswith("I")
        unresolved = [row for row in rows if row.item_report_no is None]
        assert {row.product_name for row in unresolved} == {"목이버섯", "브로콜리"}
        # The lot is still read where it could be, and left NULL on the range.
        assert sorted(str(row.lot_date) for row in unresolved) == [
            "20260101",
            "20260301",
            "20260526",
            "None",
        ]
        numbered = next(row for row in rows if row.item_report_no == "99999999999999")
        assert (numbered.report_kind, numbered.lot_date) == (None, "20260526")


@pytest.mark.asyncio
async def test_a_lot_with_one_product_resolves_however_the_recall_names_it(factory, pinned) -> None:
    """A recall of 목이버섯 against a lot that only declared 목이버섯(1kg*10) is that product."""
    async with factory() as session, session.begin():
        session.add_all([_import_label(), _import_recall("4000000005")])
    async with pinned() as session:
        service = FoodSafetyRecordService(session)
        await service.rebuild_safety_record(SYNCED_BY)
        row = (await session.execute(select(FoodSafetyRecord))).scalar_one()
        assert row.report_kind == "import"
        assert row.item_report_no is not None
        # And the declarations tab can find it back by the lot alone.
        assert await service.summarise_lots(
            "import", row.item_report_no, ["20260526", "20260828"]
        ) == {"20260526": (1, 0, "2등급")}
        assert await service.summarise_lots("import", row.item_report_no, []) == {}
