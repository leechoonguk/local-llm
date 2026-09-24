"""FoodItemReportIngredientService tests — the split rebuilt off the two 원재료 ledgers."""

import pytest
from sqlalchemy import select

from app.models.food.item_report_ingredient import FoodItemReportIngredient
from app.models.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReport,
)
from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from app.models.food.ledger_item_report_raw_material import FoodLedgerItemReportRawMaterial
from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial,
)
from app.models.food.ledger_raw_material import FoodLedgerRawMaterial
from app.services.food.item_report_ingredient import (
    FoodItemReportIngredientService,
    _ingredients,
    _Registry,
    _resolution_keys,
    _resolve,
)


SYNCED_BY = "batch:derive_food_tables"


@pytest.mark.asyncio
async def test_rebuild_splits_both_ledgers_lists_under_their_kind(factory, pinned) -> None:
    """Each ledger's lists become rows of its kind; no list, no rows; a rerun replaces.

    A record whose lists cannot be paired (more names than ordinals) keeps
    every name with no ordinal; a name listed twice is two rows told apart by
    position; and the same number under both registries is two products.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerItemReportRawMaterial(
                    item_report_no="1",
                    raw_material_names="밀가루, 정제수, 정제수",
                    raw_material_ordinals="1,2,3",
                ),
                FoodLedgerItemReportRawMaterial(
                    item_report_no="2", raw_material_names=None, raw_material_ordinals=None
                ),
                FoodLedgerLivestockItemReportRawMaterial(
                    item_report_no="1", raw_material_names="닭고기, 소금", raw_material_ordinals="1"
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodItemReportIngredientService(session)
        assert await service.rebuild_item_report_ingredient(SYNCED_BY) == 5
        assert await service.rebuild_item_report_ingredient(SYNCED_BY) == 5

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodItemReportIngredient).order_by(
                        FoodItemReportIngredient.report_kind,
                        FoodItemReportIngredient.item_report_no,
                        FoodItemReportIngredient.position,
                    )
                )
            )
            .scalars()
            .all()
        )
    assert [(r.report_kind, r.item_report_no, r.position, r.ordinal, r.name) for r in rows] == [
        ("domestic", "1", 1, 1, "밀가루"),
        ("domestic", "1", 2, 2, "정제수"),
        ("domestic", "1", 3, 3, "정제수"),
        ("livestock", "1", 1, None, "닭고기"),
        ("livestock", "1", 2, None, "소금"),
    ]


def test_split_on_the_commas_outside_parentheses() -> None:
    """A name carries its own commas inside parentheses (`혼합제제(밀가루, 정제수)`).

    Split on every comma, 12,712 C002 rows (measured 2026-09-07) would list
    more names than ordinals and lose their pairing; the separator is the
    comma outside a pair of parentheses. Names are stripped at their ends
    and kept as sent inside, empty items are dropped, and a value that is
    not a list is no list.
    """
    names = [n for _, _, n in _ingredients("밀가루, 혼합제제(밀가루, 정제수),정제수 ", None)]
    assert names == ["밀가루", "혼합제제(밀가루, 정제수)", "정제수"]
    assert [n for _, _, n in _ingredients("정제수,  ,설탕,", None)] == ["정제수", "설탕"]
    assert [n for _, _, n in _ingredients("정제수  (물)", None)] == ["정제수  (물)"]
    assert _ingredients("   ", None) == []
    assert _ingredients(None, None) == []
    assert _ingredients(["밀가루"], None) == []


def test_split_pairs_the_ordinal_to_the_name_by_position() -> None:
    """One ingredient per name, positions from 1, the ordinal at the same position.

    The pairing is by position and not by ordinal value: the provider's
    ordinals start where the product's 원재료표시순서 starts (`7,8,9`), and
    a repeated name is two ingredients because `position` is what is unique.
    """
    assert _ingredients("밀가루, 혼합제제(밀가루, 정제수), 당절임, 당절임", "7,8,9,10") == [
        (1, 7, "밀가루"),
        (2, 8, "혼합제제(밀가루, 정제수)"),
        (3, 9, "당절임"),
        (4, 10, "당절임"),
    ]


def test_split_leaves_the_ordinal_empty_when_the_lists_cannot_be_paired() -> None:
    """Lists of different lengths, or an ordinal that is no integer, pair nothing.

    5,712 C002 records (0.5%, measured 2026-09-07) list more names than
    ordinals; a pairing by position there would put a real-looking number
    on a guess, so every ingredient of such a record carries None. A record
    with no names has no ingredients, whatever its ordinals say (3 C002 rows).
    """
    assert _ingredients("밀가루, 정제수", "7") == [(1, None, "밀가루"), (2, None, "정제수")]
    assert _ingredients("밀가루, 정제수", "7,x") == [(1, None, "밀가루"), (2, None, "정제수")]
    assert _ingredients(None, "7,8") == []
    assert _ingredients("  ", None) == []


def _registry(*rows: tuple[str, str | None, str] | tuple[str, str | None, str, str]) -> _Registry:
    return _Registry([(row[0], row[1], row[2], row[3] if len(row) > 3 else None) for row in rows])


def test_resolve_ranks_exact_name_then_in_use_then_class_then_verbatim() -> None:
    """The rule the model comment states, one assertion per clause; a surviving tie is None."""
    registry = _registry(
        ("B1003622000000", "합성향료", "Y"),
        ("B1003653000000", "합성향료(바닐라향)", "Y"),
        ("B1003654000000", "합성향료(딸기향)", "Y"),
        ("A1000911010001", "밀가루", "Y"),
        ("P0129130100000", "밀가루", "Y"),
        ("B1000016000000", "구연산", "N"),
        ("B3000102000000", "구연산", "Y"),
        ("U2004425000000", "비타민 B12 혼합제제분말", "Y"),
        ("U2004435000000", "비타민B12혼합제제분말", "Y"),
        ("P0130080100000", "기타가공품", "Y"),
        ("P0130080200000", "기타가공품", "Y"),
        # Two registry rows carry no name at all (measured 2026-09-09); they index nothing.
        ("A9999999000000", None, "Y"),
    )
    # The exact name, brackets included: a flavour is its own code.
    assert _resolve(registry, "합성향료 (딸기향)") == "B1003654000000"
    # A bracket the registry does not know is the label's own note - dropped, the generic entry.
    assert _resolve(registry, "합성향료(오렌지향)") == "B1003622000000"
    # The registry's own brackets are never stripped: 합성향료 is the generic entry.
    assert _resolve(registry, "합성향료") == "B1003622000000"
    # The 원료 (A) before the 식품유형 (P) of the same name; whitespace is no difference.
    assert _resolve(registry, "밀 가루") == "A1000911010001"
    # In use before retired, whatever the class.
    assert _resolve(registry, "구연산") == "B3000102000000"
    # Two in-use codes of one class that differ only in spacing: the verbatim spelling.
    assert _resolve(registry, "비타민B12혼합제제분말") == "U2004435000000"
    assert _resolve(registry, "비타민 B12 혼합제제분말") == "U2004425000000"
    # Two in-use codes of one class spelled alike: not a guess.
    assert _resolve(registry, "기타가공품") is None
    assert _resolve(registry, "정제수") is None


def test_split_counts_bracket_depth() -> None:
    """A comma inside nested brackets is part of the name, not a separator."""
    names, _ = zip(
        *[
            (name, ordinal)
            for _, ordinal, name in _ingredients(
                "합성향료(4-Hydroxy-2, 5-dimethyl-3(2H)-furanone), 정제수", "1,2"
            )
        ],
        strict=True,
    )
    assert list(names) == ["합성향료(4-Hydroxy-2, 5-dimethyl-3(2H)-furanone)", "정제수"]


@pytest.mark.asyncio
async def test_rebuild_stamps_each_name_with_the_material_it_resolves_to(factory, pinned) -> None:
    """The code is decided at write time off the I2520 ledger, NULL where it cannot be."""
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerRawMaterial(
                    raw_material_code="A1000911010001",
                    representative_raw_material_name="밀가루",
                    use_yn="Y",
                ),
                # A 위생용품 code of the same name is no candidate: not a class food is made of.
                FoodLedgerRawMaterial(
                    raw_material_code="E0000100000000",
                    representative_raw_material_name="정제수",
                    use_yn="Y",
                ),
                FoodLedgerItemReportRawMaterial(
                    item_report_no="1",
                    raw_material_names="밀가루, 정제수",
                    raw_material_ordinals="1,2",
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodItemReportIngredientService(session)
        assert await service.rebuild_item_report_ingredient(SYNCED_BY) == 2

    async with factory() as session:
        rows = (
            await session.execute(
                select(
                    FoodItemReportIngredient.name, FoodItemReportIngredient.material_code
                ).order_by(FoodItemReportIngredient.position)
            )
        ).all()
    assert [tuple(row) for row in rows] == [("밀가루", "A1000911010001"), ("정제수", None)]


@pytest.mark.asyncio
async def test_the_import_slice_reads_the_newest_printed_list(factory, pinned) -> None:
    """An imported product's ingredients are the printed list of its newest declaration.

    The feed's own 원재료 column is filled on 0.7% of declarations; the printed
    label carries the list on 47.8%, so that is what is read - from the newest
    declaration, because the list belongs to the package. `ordinal` is None:
    a printed list has an order but no published 원재료표시순서.
    """
    printed = "원재료명 : 정제수, 설탕 보관방법 : 실온"
    newer = "원재료명 : 정제수, 과당, 구연산 보관방법 : 실온"
    async with factory() as session, session.begin():
        session.add_all(
            [
                FoodLedgerImportFoodLabel(
                    declaration_kind="가공식품",
                    importer_name="수입사",
                    product_name="음료",
                    product_name_en="DRINK",
                    product_type_name="음료류",
                    overseas_maker_name="MAKER",
                    origin_country="중국",
                    export_country="중국",
                    processed_date="20240101",
                    expiry_text="A",
                    label_text=printed,
                    created_by="test",
                    updated_by="test",
                ),
                FoodLedgerImportFoodLabel(
                    declaration_kind="가공식품",
                    importer_name="수입사",
                    product_name="음료",
                    product_name_en="DRINK",
                    product_type_name="음료류",
                    overseas_maker_name="MAKER",
                    origin_country="중국",
                    export_country="중국",
                    processed_date="20260911",
                    expiry_text="B",
                    label_text=newer,
                    created_by="test",
                    updated_by="test",
                ),
                # Declared again the same day with another list: the tie keeps
                # what is held, so a product never mixes two packages' lists.
                FoodLedgerImportFoodLabel(
                    declaration_kind="가공식품",
                    importer_name="수입사",
                    product_name="음료",
                    product_name_en="DRINK",
                    product_type_name="음료류",
                    overseas_maker_name="MAKER",
                    origin_country="중국",
                    export_country="중국",
                    processed_date="20260911",
                    expiry_text="C",
                    label_text="원재료명 : 정제수",
                    created_by="test",
                    updated_by="test",
                ),
            ]
        )

    async with pinned() as session:
        written = await FoodItemReportIngredientService(session).rebuild_item_report_ingredient(
            SYNCED_BY
        )
    assert written == 3

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodItemReportIngredient)
                    .where(FoodItemReportIngredient.report_kind == "import")
                    .order_by(FoodItemReportIngredient.position)
                )
            )
            .scalars()
            .all()
        )
        assert [row.name for row in rows] == ["정제수", "과당", "구연산"]
        assert {row.ordinal for row in rows} == {None}
        assert {row.item_report_no.startswith("I") for row in rows} == {True}


@pytest.mark.asyncio
async def test_a_declaration_printing_no_list_leaves_the_product_without_ingredients(
    factory, pinned
) -> None:
    """52.2% of declarations print no 원재료 section; a product with none gets no rows."""
    async with factory() as session, session.begin():
        session.add(
            FoodLedgerImportFoodLabel(
                declaration_kind="가공식품",
                importer_name="수입사",
                product_name="음료",
                product_name_en="DRINK",
                product_type_name="음료류",
                overseas_maker_name="MAKER",
                origin_country="중국",
                export_country="중국",
                processed_date="20260911",
                expiry_text="A",
                label_text=None,
                created_by="test",
                updated_by="test",
            )
        )

    async with pinned() as session:
        assert (
            await FoodItemReportIngredientService(session).rebuild_item_report_ingredient(SYNCED_BY)
            == 0
        )


def test_a_printed_name_is_looked_up_under_what_the_label_added() -> None:
    """The 표시기준 prints things around a name that the registry does not carry.

    Every rule here is one shape from the unresolved list, measured 2026-09-14
    over 126,321 import ingredient rows that resolved to nothing: the allergen
    note in brackets (2,313 rows on 냉동돼지고기 alone), the 용도 in either
    position (877 and 274), the 5' the printing dropped (991), the roman numeral
    in the other alphabet (442 and 372) and the three measured aliases.
    """
    assert "냉동돼지고기" in _resolution_keys("냉동돼지고기 [돼지고기 함유]")
    assert "무수아황산" in _resolution_keys("무수아황산(산화방지제) [이산화황 함유]")
    assert "소브산칼륨" in _resolution_keys("보존료(소브산칼륨)")
    assert "5-리보뉴클레오티드이나트륨" in _resolution_keys("'-리보뉴클레오티드이나트륨")
    assert "카라멜색소I" in _resolution_keys("카라멜색소Ⅰ")
    assert "카라멜색소Ⅳ" in _resolution_keys("카라멜색소IV")
    assert "고춧가루" in _resolution_keys("고추가루")
    # The printed name itself is always the first key, and the row keeps it.
    assert _resolution_keys("정제수")[0] == "정제수"


def test_a_published_alias_resolves_what_the_representative_name_does_not() -> None:
    """The registry states its own 이명, and a label prints those.

    15,825 of the registry's 42,432 rows carry a comma-joined 이명 list
    (2026-09-14): 우유응고효소 lists RENNET/레넷/렌넷 (833 unresolved rows),
    d-α-토코페롤 lists sixty spellings of itself (364 + 123). Matched without
    spaces and case-insensitively, and a published alias on two codes is still
    a tie, so it stays NULL.
    """
    registry = _registry(
        ("B2000017000000", "우유응고효소", "Y", "RENNET,Chymosin,RENNET,레넷,렌넷"),
        ("B1000123000000", "d-α-토코페롤", "Y", "D-a-토코페롤,디알파토코페롤"),
        ("B1000999000000", "이명중복A", "Y", "겹치는이름"),
        ("B1000998000000", "이명중복B", "Y", "겹치는이름"),
    )
    assert _resolve(registry, "렌넷") == "B2000017000000"
    assert _resolve(registry, "d-a-토코페롤") == "B1000123000000"
    assert _resolve(registry, "겹치는이름") is None
    # The registry repeats an alias within one row; that is one code, not a tie.
    assert _resolve(registry, "rennet") == "B2000017000000"


def test_a_use_written_as_a_trailing_bracket_is_not_part_of_the_name() -> None:
    """포도원액(무수아황산(산화방지제)) is 포도원액 - 3,935 rows, measured 2026-09-14."""
    registry = _registry(("A1000001000000", "포도원액", "Y"))
    assert _resolve(registry, "포도원액(무수아황산(산화방지제))") == "A1000001000000"
    assert _resolve(registry, "포도원액 (무수아황산(산화방지제))") == "A1000001000000"


@pytest.mark.asyncio
async def test_the_three_health_functional_lists_carry_their_role(factory, pinned) -> None:
    """건강기능식품 publishes three 원재료 lists where the others publish one.

    Measured 2026-09-15 over 46,086 reports: 기능성 46,084, 기타 41,764, 캡슐
    12,482. They are numbered as one sequence in that order, and the row says
    which list it came from - a reader asking for the functional ones must not
    get the capsule shell.
    """
    async with factory() as session, session.begin():
        session.add_all(
            [
                FoodLedgerHealthFunctionalItemReport(
                    item_report_no="H1",
                    functional_raw_material_names="Lactobacillus acidophilus(고시형), 비타민C",
                    other_raw_material_names="정제수, 설탕",
                    capsule_raw_material_names="젤라틴",
                    created_by="test",
                    updated_by="test",
                ),
                FoodLedgerRawMaterial(
                    raw_material_code="A1000001000000",
                    representative_raw_material_name="정제수",
                ),
            ]
        )

    async with pinned() as session:
        written = await FoodItemReportIngredientService(session).rebuild_item_report_ingredient(
            SYNCED_BY
        )
    assert written == 5

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodItemReportIngredient).order_by(FoodItemReportIngredient.position)
                )
            )
            .scalars()
            .all()
        )
        assert [(r.position, r.ingredient_role, r.name) for r in rows] == [
            (1, "functional", "Lactobacillus acidophilus(고시형)"),
            (2, "functional", "비타민C"),
            (3, "other", "정제수"),
            (4, "other", "설탕"),
            (5, "capsule", "젤라틴"),
        ]
        assert {r.report_kind for r in rows} == {"health_functional"}
        assert [r.material_code for r in rows if r.name == "정제수"] == ["A1000001000000"]
