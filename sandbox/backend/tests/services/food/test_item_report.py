"""FoodItemReportService tests — the rebuild off the two report ledgers, and the ingredient edge."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundError
from app.models.food.common_standard_type import FoodCommonStandardType
from app.models.food.item_report import FoodItemReport
from app.models.food.item_report_ingredient import FoodItemReportIngredient
from app.models.food.label import FoodLabel
from app.models.food.label_allergen import FoodLabelAllergen
from app.models.food.label_caution import FoodLabelCaution
from app.models.food.label_packaging import FoodLabelPackaging
from app.models.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReport,
)
from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from app.models.food.ledger_item_report import FoodLedgerItemReport
from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial,
)
from app.models.food.product_classification import FoodProductClassification
from app.models.food.raw_material import FoodRawMaterial
from app.models.food.standard import FoodStandard
from app.schemas.food.item_report import FoodItemReportFilter
from app.services.food.item_report import FoodItemReportService


SYNCED_BY = "batch:derive_food_tables"


@pytest.mark.asyncio
async def test_rebuild_writes_both_registries_each_with_what_it_publishes(factory, pinned) -> None:
    """A food row is I1250 column for column; a livestock row is C006's six and eleven NULLs.

    The two registries number their reports in separate spaces, so the same
    number under both kinds is two rows - and the eleven columns C006 does
    not publish stay NULL rather than being filled from somewhere else.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerItemReport(
                    item_report_no="1",
                    product_name="진미순간장",
                    product_type_name="혼합간장",
                    shelf_life="제조일로부터 24개월",
                    usage_method="조리시 적절하게 첨가하여 이용한다",
                    domestic_export_type="O",
                ),
                FoodLedgerLivestockItemReportRawMaterial(
                    item_report_no="1",
                    business_name="노벨유통",
                    product_name="닭꼬치",
                    product_type_name="포장육",
                    raw_material_names="닭고기",
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        assert await FoodItemReportService(session).rebuild_item_report(SYNCED_BY) == 2

    async with factory() as session:
        food, livestock = (
            (await session.execute(select(FoodItemReport).order_by(FoodItemReport.report_kind)))
            .scalars()
            .all()
        )
    assert (food.report_kind, food.item_report_no, food.shelf_life, food.domestic_export_type) == (
        "domestic",
        "1",
        "제조일로부터 24개월",
        "O",
    )
    assert (livestock.report_kind, livestock.business_name, livestock.product_type_name) == (
        "livestock",
        "노벨유통",
        "포장육",
    )
    assert [
        livestock.shelf_life,
        livestock.product_form,
        livestock.packaging_material,
        livestock.usage_method,
        livestock.purpose,
        livestock.industry_name,
        livestock.quality_maintenance_days,
        livestock.production_ended,
        livestock.high_calorie_low_nutrition,
        livestock.child_favorite_certified_yn,
        livestock.domestic_export_type,
    ] == [None] * 11


@pytest.mark.asyncio
async def test_report_and_ingredient_resolve_each_other_within_one_kind(factory) -> None:
    """The edge is both columns: a number alone names a row in each registry.

    The two registries number their reports in separate spaces, so a `livestock`
    row carrying the same number as a `food` one is a different product - and the
    ingredients come back in the order the label lists them, not the row order.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodItemReport(report_kind="domestic", item_report_no="1", product_name="찐빵"),
                FoodItemReport(report_kind="livestock", item_report_no="1", product_name="소시지"),
                FoodItemReportIngredient(
                    report_kind="domestic", item_report_no="1", position=2, name="정제수"
                ),
                FoodItemReportIngredient(
                    report_kind="domestic", item_report_no="1", position=1, name="밀가루"
                ),
                FoodItemReportIngredient(
                    report_kind="livestock", item_report_no="1", position=1, name="돼지고기"
                ),
            ]
        )
        await session.commit()

    async with factory() as session:
        reports = (
            (
                await session.execute(
                    select(FoodItemReport)
                    .options(joinedload(FoodItemReport.ingredients))
                    .order_by(FoodItemReport.report_kind)
                )
            )
            .unique()
            .scalars()
            .all()
        )
        ingredients = (
            (
                await session.execute(
                    select(FoodItemReportIngredient)
                    .options(joinedload(FoodItemReportIngredient.report))
                    .order_by(
                        FoodItemReportIngredient.report_kind,
                        FoodItemReportIngredient.position,
                    )
                )
            )
            .scalars()
            .all()
        )

    assert [(r.report_kind, [i.name for i in r.ingredients]) for r in reports] == [
        ("domestic", ["밀가루", "정제수"]),
        ("livestock", ["돼지고기"]),
    ]
    assert [(i.name, i.report and i.report.product_name) for i in ingredients] == [
        ("밀가루", "찐빵"),
        ("정제수", "찐빵"),
        ("돼지고기", "소시지"),
    ]


@pytest.mark.asyncio
async def test_list_and_count_agree_under_the_same_filters(factory) -> None:
    """The page and its total are one predicate: text fields a fragment, the kind exact."""
    async with factory() as session:
        session.add_all(
            [
                FoodItemReport(report_kind="domestic", item_report_no="2", product_name="단팥빵"),
                FoodItemReport(report_kind="domestic", item_report_no="1", product_name="찐빵"),
                FoodItemReport(
                    report_kind="livestock", item_report_no="3", product_name="빵 소시지"
                ),
            ]
        )
        await session.commit()

    async with factory() as session:
        service = FoodItemReportService(session)
        everything = await service.list_item_reports()
        assert [(r.report_kind, r.item_report_no) for r in everything] == [
            ("domestic", "1"),
            ("domestic", "2"),
            ("livestock", "3"),
        ]
        assert await service.count_item_reports() == 3

        narrowed = FoodItemReportFilter(product_name="빵", report_kind="domestic")
        first_page = await service.list_item_reports(0, 1, narrowed)
        assert [r.item_report_no for r in first_page] == ["1"]
        assert await service.count_item_reports(narrowed) == 2


@pytest.mark.asyncio
async def test_facets_are_the_type_names_the_table_holds(factory) -> None:
    """A select offers what a row can match: each name once, sorted, NULL left out."""
    async with factory() as session:
        session.add_all(
            [
                FoodItemReport(
                    report_kind="domestic", item_report_no="1", product_type_name="모든음료"
                ),
                FoodItemReport(report_kind="domestic", item_report_no="2", product_type_name=None),
                FoodItemReport(
                    report_kind="livestock", item_report_no="3", product_type_name="가공육제품"
                ),
                FoodItemReport(
                    report_kind="livestock", item_report_no="4", product_type_name="가공육제품"
                ),
            ]
        )
        await session.commit()

    async with factory() as session:
        facets = await FoodItemReportService(session).list_item_report_facets()
    assert facets.product_type_name == ["가공육제품", "모든음료"]

    async with factory() as session:
        service = FoodItemReportService(session)
        picked = FoodItemReportFilter(product_type_name=facets.product_type_name[0])
        assert [r.item_report_no for r in await service.list_item_reports(0, 10, picked)] == [
            "3",
            "4",
        ]
        # Whole-value: a fragment of a name is not a name the reader picked.
        fragment = FoodItemReportFilter(product_type_name="가공육")
        assert await service.count_item_reports(fragment) == 0


@pytest.mark.asyncio
async def test_get_item_report_loads_its_edges_or_raises_not_found(factory) -> None:
    """One report comes with its ingredients in label order; a missing id is NotFoundError."""
    async with factory() as session:
        session.add_all(
            [
                FoodItemReport(report_kind="domestic", item_report_no="1", product_name="찐빵"),
                FoodItemReportIngredient(
                    report_kind="domestic", item_report_no="1", position=2, name="설탕"
                ),
                FoodItemReportIngredient(
                    report_kind="domestic", item_report_no="1", position=1, name="밀가루"
                ),
            ]
        )
        await session.commit()
        (report_id,) = (await session.execute(select(FoodItemReport.id))).scalars().all()

    async with factory() as session:
        service = FoodItemReportService(session)
        report = await service.get_item_report(report_id)
        assert [i.name for i in report.ingredients] == ["밀가루", "설탕"]
        assert report.nutritions == []
        with pytest.raises(NotFoundError):
            await service.get_item_report(uuid4())


def _node(code: str, name: str, parent: str | None, level: str) -> FoodProductClassification:
    return FoodProductClassification(
        product_code=code,
        korean_name=name,
        product_yn="Y" if level == "4" else "N",
        parent_product_code=parent,
        level=level,
    )


def _common(seq: str, product_code: str, heading: str, item: str) -> FoodStandard:
    return FoodStandard(
        standard_kind="common",
        standard_seq=seq,
        product_code=product_code,
        common_standard_type_code=heading,
        test_item_code=item,
        detail_item_name="",
        clause_seq="1",
    )


@pytest.mark.asyncio
async def test_standards_walk_the_tree_root_first(factory) -> None:
    """A type's 제5 clauses are its own; its 제2 clauses come down the path, root's first.

    빵류 sits under 과자류·빵류 under 가공식품. It carries one individual clause
    and inherits every common clause on the path - two from the root, one from
    the tier, one written on itself - each with the node it came from and the
    heading path it hangs on.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodItemReport(
                    report_kind="domestic", item_report_no="1", product_type_name="빵류"
                ),
                _node("C0000000000000", "가공식품", None, "1"),
                _node("C0301000000000", "과자류·빵류", "C0000000000000", "3"),
                _node("C0301040000000", "빵류", "C0301000000000", "4"),
                FoodCommonStandardType(common_standard_type_code="000095", standard_name="제2"),
                FoodCommonStandardType(
                    common_standard_type_code="000140",
                    standard_name="(2) 별표",
                    parent_common_standard_type_code="000095",
                ),
                FoodStandard(
                    standard_kind="individual",
                    standard_seq="1",
                    test_item_code="C10001",
                    detail_item_name="",
                    clause_seq="1",
                    product_code="C0301040000000",
                    standard_value="1.0 이하",
                ),
                _common("1", "C0000000000000", "000140", "C20001"),
                _common("2", "C0000000000000", "000140", "C20002"),
                _common("3", "C0301000000000", "000140", "C20003"),
                _common("4", "C0301040000000", "000095", "C20004"),
            ]
        )
        await session.commit()
        (report_id,) = (await session.execute(select(FoodItemReport.id))).scalars().all()

    async with factory() as session:
        (entry,) = await FoodItemReportService(session).get_item_report_standards(report_id)

    assert [n.korean_name for n in entry.path] == ["가공식품", "과자류·빵류", "빵류"]
    assert [s.standard_value for s in entry.individual_standards] == ["1.0 이하"]
    inherited = [
        (
            c.standard.standard_seq,
            c.inherited_from.korean_name,
            [h.standard_name for h in c.heading_path],
        )
        for c in entry.common_standards
    ]
    assert inherited == [
        ("1", "가공식품", ["제2", "(2) 별표"]),
        ("2", "가공식품", ["제2", "(2) 별표"]),
        ("3", "과자류·빵류", ["제2", "(2) 별표"]),
        ("4", "빵류", ["제2"]),
    ]


def _ingredient(
    kind: str, no: str, position: int, name: str, code: str
) -> FoodItemReportIngredient:
    return FoodItemReportIngredient(
        report_kind=kind, item_report_no=no, position=position, name=name, material_code=code
    )


@pytest.mark.asyncio
async def test_item_reports_by_material_answer_each_product_once(factory) -> None:
    """A label repeating the name is one product; another material none; unknown id not found."""
    async with factory() as session:
        session.add_all(
            [
                FoodRawMaterial(
                    raw_material_code="A1000911010001",
                    base_code="A1000911",
                    representative_raw_material_name="밀가루",
                ),
                FoodRawMaterial(
                    raw_material_code="A1000911280000",
                    base_code="A1000911",
                    representative_raw_material_name="밀기울",
                ),
                FoodItemReport(report_kind="domestic", item_report_no="1", product_name="찐빵"),
                FoodItemReport(report_kind="domestic", item_report_no="2", product_name="식빵"),
                FoodItemReport(report_kind="livestock", item_report_no="3", product_name="소시지"),
                _ingredient("domestic", "1", 1, "밀가루", "A1000911010001"),
                _ingredient("domestic", "1", 2, "밀가루", "A1000911010001"),
                _ingredient("domestic", "2", 1, "밀기울", "A1000911280000"),
                _ingredient("livestock", "3", 1, "밀가루", "A1000911010001"),
            ]
        )
        await session.commit()
        flour = await session.scalar(
            select(FoodRawMaterial).where(FoodRawMaterial.raw_material_code == "A1000911010001")
        )
        assert flour is not None

    async with factory() as session:
        service = FoodItemReportService(session)
        reports = await service.list_item_reports_by_raw_material(flour.id, 0, 10)
        assert [(r.report_kind, r.item_report_no) for r in reports] == [
            ("domestic", "1"),
            ("livestock", "3"),
        ]
        assert await service.count_item_reports_by_raw_material(flour.id) == 2
        second = await service.list_item_reports_by_raw_material(flour.id, 1, 10)
        assert [r.item_report_no for r in second] == ["3"]
        with pytest.raises(NotFoundError):
            await service.list_item_reports_by_raw_material(uuid4(), 0, 10)


@pytest.mark.asyncio
async def test_labels_of_a_report_carry_their_own_rows_and_no_siblings(factory) -> None:
    """Each label answers with the rows keyed to it, and to no sibling label."""
    async with factory() as session:
        report = FoodItemReport(
            report_kind="domestic", item_report_no="1", product_name="대추차플러스"
        )
        session.add_all(
            [
                report,
                FoodLabel(source="food-qr", label_key="L1", item_report_no="1"),
                FoodLabel(source="haccp", label_key="1", item_report_no="1"),
                FoodLabel(source="food-qr", label_key="L9", item_report_no="2"),
                FoodLabelAllergen(source="food-qr", label_key="L1", position=1, name="대두"),
                FoodLabelAllergen(source="haccp", label_key="1", position=1, name="밀"),
                FoodLabelAllergen(source="food-qr", label_key="L9", position=1, name="우유"),
                FoodLabelCaution(source="food-qr", label_key="L1", position=1, caution_text="1399"),
                FoodLabelPackaging(
                    source="food-qr", label_key="L1", position=1, packaging_text="폴리프로필렌"
                ),
            ]
        )
        await session.commit()
        report_id = report.id

    async with factory() as session:
        panels = await FoodItemReportService(session).get_item_report_labels(report_id)

    assert [(p.label.source, p.label.label_key) for p in panels] == [
        ("food-qr", "L1"),
        ("haccp", "1"),
    ]
    assert [[a.name for a in p.allergens] for p in panels] == [["대두"], ["밀"]]
    # Only 푸드QR publishes cautions and packaging parts, so the HACCP label has none.
    assert [[c.caution_text for c in p.cautions] for p in panels] == [["1399"], []]
    assert [[k.packaging_text for k in p.packagings] for p in panels] == [["폴리프로필렌"], []]


@pytest.mark.asyncio
async def test_labels_of_a_report_with_none_is_an_empty_list(factory) -> None:
    """Most reports have no label, and a report that is not there is still a 404."""
    async with factory() as session:
        report = FoodItemReport(report_kind="domestic", item_report_no="9", product_name="라벨없음")
        session.add(report)
        await session.commit()
        report_id = report.id

    async with factory() as session:
        service = FoodItemReportService(session)
        assert await service.get_item_report_labels(report_id) == []
        with pytest.raises(NotFoundError):
            await service.get_item_report_labels(uuid4())


@pytest.mark.asyncio
async def test_the_import_slice_is_one_row_per_product_from_its_newest_declaration(
    factory, pinned
) -> None:
    """1,055,682 declarations are 292,867 products: the key is five columns, the row is the newest.

    A product's number is the digest of those five, so the same product read
    from any of its declarations is one row - and what the row carries is the
    newest declaration's, because that is what "as of" means for a product.
    """
    async with factory() as session, session.begin():
        session.add_all(
            [
                FoodLedgerImportFoodLabel(
                    declaration_kind="가공식품",
                    importer_name="쏠트코리아",
                    product_name="천일염",
                    product_name_en="SEA SALT",
                    product_type_name="천일염",
                    overseas_maker_name="UBAIDIA",
                    origin_country="파키스탄",
                    export_country="파키스탄",
                    processed_date="20200508",
                    expiry_text="A",
                    created_by="test",
                    updated_by="test",
                ),
                FoodLedgerImportFoodLabel(
                    declaration_kind="가공식품",
                    importer_name="쏠트코리아",
                    product_name="천일염",
                    product_name_en="SEA SALT",
                    product_type_name="천일염",
                    overseas_maker_name="UBAIDIA",
                    origin_country="파키스탄",
                    export_country="파키스탄",
                    processed_date="20260911",
                    expiry_text="B",
                    created_by="test",
                    updated_by="test",
                ),
                FoodLedgerImportFoodLabel(
                    declaration_kind="가공식품",
                    importer_name="쏠트코리아",
                    product_name="천일염",
                    product_name_en="SEA SALT",
                    product_type_name="천일염",
                    overseas_maker_name="OTHER",
                    origin_country="파키스탄",
                    export_country="파키스탄",
                    processed_date="20250101",
                    expiry_text="C",
                    created_by="test",
                    updated_by="test",
                ),
            ]
        )

    async with pinned() as session:
        assert await FoodItemReportService(session).rebuild_item_report(SYNCED_BY) == 2

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodItemReport)
                    .where(FoodItemReport.report_kind == "import")
                    .order_by(FoodItemReport.report_date)
                )
            )
            .scalars()
            .all()
        )
        assert [row.report_date for row in rows] == ["20250101", "20260911"]
        assert {row.business_name for row in rows} == {"쏠트코리아"}
        # One column, one meaning: 보고 업소 is the 수입업체, 제조업소 the 해외
        # 제조업소, 제조국 the declared country, and 소비기한 the printed 유통기한.
        assert {row.maker_name for row in rows} == {"UBAIDIA", "OTHER"}
        assert {row.origin_country for row in rows} == {"파키스탄"}
        assert {row.product_name_en for row in rows} == {"SEA SALT"}
        # 소비기한 is a period a domestic report states; this registry answers a
        # range between two dates, which is the declaration's fact and stays
        # on `food_item_report_declaration` rather than under a name that means
        # something else here.
        assert {row.shelf_life for row in rows} == {None}
        # The 품목제조보고 columns the import registry does not publish stay NULL.
        assert all(row.license_no is None and row.industry_name is None for row in rows)
        assert all(row.item_report_no.startswith("I") for row in rows)


@pytest.mark.asyncio
async def test_a_crossing_that_is_not_a_product_reaches_no_derived_table(factory, pinned) -> None:
    """The 수입신고 ledger is every crossing; a product is what a registry can name.

    브로콜리(신선) is an HS commodity, a 냉동 정육 a quarantine class, a
    COFFEE GRINDER not food - none has a 식품유형 the 품목제조보고 registries
    use (measured: 0 %, 19 %, 2 % of those kinds' rows share the vocabulary,
    against 95 % of 가공식품). They stay in the ledger and derive nothing.
    """

    def crossing(kind: str, name: str, type_name: str) -> FoodLedgerImportFoodLabel:
        return FoodLedgerImportFoodLabel(
            declaration_kind=kind,
            importer_name="수입사",
            product_name=name,
            product_name_en=name,
            product_type_name=type_name,
            overseas_maker_name="MAKER",
            origin_country="중국",
            export_country="중국",
            processed_date="20260901",
            expiry_text="20260901 ~ 20280831",
            label_text="원재료명 : 정제수",
            created_by="test",
            updated_by="test",
        )

    async with factory() as session, session.begin():
        session.add_all(
            [
                crossing("농.임산물", "브로콜리", "브로콜리(신선)"),
                crossing("축산물", "냉동 정육", "돼지고기(냉동,정육(뼈없는것))"),
                crossing("기구또는용기.포장", "COFFEE GRINDER", "폴리프로필렌"),
                crossing("가공식품", "커피", "볶은커피"),
            ]
        )

    async with pinned() as session:
        assert await FoodItemReportService(session).rebuild_item_report(SYNCED_BY) == 1

    async with factory() as session:
        rows = (await session.execute(select(FoodItemReport))).scalars().all()
        assert [row.product_name for row in rows] == ["커피"]


@pytest.mark.asyncio
async def test_two_declarations_of_one_day_keep_the_first_read(factory, pinned) -> None:
    """A product declared twice on one day is still one row: the tie keeps what is held."""
    async with factory() as session, session.begin():
        session.add_all(
            [
                FoodLedgerImportFoodLabel(
                    declaration_kind="가공식품",
                    importer_name="쏠트코리아",
                    product_name="천일염",
                    product_name_en="SEA SALT",
                    product_type_name="천일염",
                    overseas_maker_name="UBAIDIA",
                    origin_country="파키스탄",
                    export_country="파키스탄",
                    processed_date="20260911",
                    expiry_text=expiry,
                    created_by="test",
                    updated_by="test",
                )
                for expiry in ("A", "B")
            ]
        )

    async with pinned() as session:
        assert await FoodItemReportService(session).rebuild_item_report(SYNCED_BY) == 1


@pytest.mark.asyncio
async def test_the_health_functional_slice_fills_the_same_columns(factory, pinned) -> None:
    """건강기능식품 (46,086 reports, 2026-09-15) is the fourth registry, not a fourth shape.

    Its 허가일자 is 보고일자 here, its 업소 is both the 보고 업소 and the
    제조업소, its 제조국 is 대한민국, and the four columns nothing else publishes
    (주된기능성, 섭취시주의사항, 보관방법, 기준규격, 기능지표성분) are its own.
    """
    async with factory() as session, session.begin():
        session.add(
            FoodLedgerHealthFunctionalItemReport(
                item_report_no="20140017002183",
                product_name="11종 혼합유산균",
                business_name="일동바이오사이언스(주)",
                license_no="20140017002",
                permit_date="20201027",
                product_type_name="프로바이오틱스",
                primary_functionality="유산균 증식에 도움을 줄 수 있음",
                intake_caution="질환이 있으면 전문가와 상담하십시오.",
                storage_method="직사광선을 피해 보관",
                standard_spec="대장균군 : 음성",
                functional_indicator="프로바이오틱스, 아연",
                shelf_life="제조일로부터 24개월까지",
                industry_name="건강기능식품전문제조업",
                production_ended="아니오",
                created_by="test",
                updated_by="test",
            )
        )

    async with pinned() as session:
        assert await FoodItemReportService(session).rebuild_item_report(SYNCED_BY) == 1

    async with factory() as session:
        row = (await session.execute(select(FoodItemReport))).scalar_one()
        assert row.report_kind == "health_functional"
        assert row.report_date == "20201027"
        assert row.business_name == row.maker_name == "일동바이오사이언스(주)"
        assert row.origin_country == "대한민국"
        assert row.primary_functionality == "유산균 증식에 도움을 줄 수 있음"
        assert row.standard_spec == "대장균군 : 음성"
        # 기능지표성분 is a field of the product, not ingredient rows: it is the
        # 고시형 axis the claim is indexed on, and only 45.2% of its names
        # resolve against the 원재료 dictionary (2026-09-15).
        assert row.functional_indicator == "프로바이오틱스, 아연"
        # Nothing of the import registry leaks in.
        assert row.product_name_en is None
