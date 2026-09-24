"""The import slice of the label family - a printed paragraph read into four tables.

The import feed publishes no fields, only the label as it is printed (1,044,332
of 1,055,682 declarations, 2026-09-14), so every row here is what
`core/printed_label.py` read out of one.
"""

import pytest
from sqlalchemy import select

from app.models.food.label import FoodLabel
from app.models.food.label_allergen import FoodLabelAllergen
from app.models.food.label_caution import FoodLabelCaution
from app.models.food.label_packaging import FoodLabelPackaging
from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from app.services.food.label_family import FoodLabelFamilyService


SYNCED_BY = "batch:derive_food_tables"


async def _declaration(
    factory, *, label_text: str | None, processed_date: str, expiry: str | None = None
) -> None:
    """One more declaration of the same product, on its own 처리일자."""
    async with factory() as session, session.begin():
        session.add(
            FoodLedgerImportFoodLabel(
                importer_name="쏠트코리아",
                product_name="살라미",
                product_name_en="SALAMI",
                product_type_name="소시지",
                overseas_maker_name="ESPUNA",
                origin_country="스페인",
                export_country="스페인",
                processed_date=processed_date,
                expiry_text=expiry or f"{processed_date} ~ 20280101",
                declaration_kind="가공식품",
                label_text=label_text,
                created_by="test",
                updated_by="test",
            )
        )


async def _ledger(factory, *, label_text: str | None) -> None:
    async with factory() as session, session.begin():
        session.add(
            FoodLedgerImportFoodLabel(
                importer_name="쏠트코리아",
                product_name="살라미",
                product_name_en="SALAMI",
                product_type_name="소시지",
                overseas_maker_name="ESPUNA",
                origin_country="스페인",
                export_country="스페인",
                processed_date="20260911",
                expiry_text="20260101 ~ 20280101",
                declaration_kind="가공식품",
                label_text=label_text,
                created_by="test",
                updated_by="test",
            )
        )


PRINTED = (
    "식품위생법에 의한 한글표시사항 "
    "원재료명 : 돼지고기, 유당(우유), 정제소금 "
    "보관방법 : 냉장보관(0~10℃) "
    "포장재질 : 저밀도폴리에틸렌, 알루미늄 "
    "주의사항 : 개봉 후 빨리, 어린이 손이 닿지 않는 곳 "
    "내용량 : 100g "
    "돼지고기, 우유 함유"
)


@pytest.mark.asyncio
async def test_a_printed_label_becomes_a_label_row(factory, pinned) -> None:
    """The sections a reader wants land in the columns the other portals fill as fields."""
    await _ledger(factory, label_text=PRINTED)

    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)

    async with factory() as session:
        row = (await session.execute(select(FoodLabel))).scalar_one()
        assert row.source == "import"
        assert row.label_key.startswith("I")
        # One product, one printed label: the key is the product's number, and
        # the label row and the report row are the same number.
        assert row.label_key == row.item_report_no
        assert row.storage_text == "냉장보관(0~10℃)"
        assert row.content_amount_text == "100g"
        assert row.raw_material_text == "돼지고기, 유당(우유), 정제소금"
        assert row.business_name == "쏠트코리아"
        assert row.maker_name == "ESPUNA"
        # A printed 함유 phrase is a declaration; a label with neither is UNKNOWN.
        assert row.allergen_declaration == "declared"


@pytest.mark.asyncio
async def test_a_declaration_without_a_printed_label_gets_no_row(factory, pinned) -> None:
    """11,350 declarations print nothing (2026-09-14); a label of nothing is not a label."""
    await _ledger(factory, label_text=None)

    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)
    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)
    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)


@pytest.mark.asyncio
async def test_the_children_are_the_printed_lists(factory, pinned) -> None:
    """Allergens, cautions and packaging parts are numbered as the label prints them."""
    await _ledger(factory, label_text=PRINTED)

    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)
    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)
    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)

    async with factory() as session:
        allergens = (
            (await session.execute(select(FoodLabelAllergen).order_by(FoodLabelAllergen.position)))
            .scalars()
            .all()
        )
        assert [row.name for row in allergens] == ["돼지고기", "우유"]
        packagings = (
            (
                await session.execute(
                    select(FoodLabelPackaging).order_by(FoodLabelPackaging.position)
                )
            )
            .scalars()
            .all()
        )
        assert [row.packaging_text for row in packagings] == ["저밀도폴리에틸렌", "알루미늄"]
        cautions = (
            (await session.execute(select(FoodLabelCaution).order_by(FoodLabelCaution.position)))
            .scalars()
            .all()
        )
        printed_cautions = ["개봉 후 빨리", "어린이 손이 닿지 않는 곳"]
        assert [row.caution_text for row in cautions] == printed_cautions
        assert {row.source for row in (*allergens, *packagings, *cautions)} == {"import"}


@pytest.mark.asyncio
async def test_an_allergen_section_is_read_before_the_함유_phrase(factory, pinned) -> None:
    """A label that prints 알레르기 as a section needs no 함유 sentence to declare."""
    await _ledger(
        factory,
        label_text="원재료명 : 밀가루 알레르기 : 밀, 대두 보관방법 : 실온",
    )

    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)
    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)

    async with factory() as session:
        label = (await session.execute(select(FoodLabel))).scalar_one()
        assert label.allergen_declaration == "declared"
        rows = (
            (await session.execute(select(FoodLabelAllergen).order_by(FoodLabelAllergen.position)))
            .scalars()
            .all()
        )
        assert [row.name for row in rows] == ["밀", "대두"]


@pytest.mark.asyncio
async def test_a_label_declaring_nothing_is_unknown_not_none(factory, pinned) -> None:
    """Most printed labels say nothing about allergens; silence is not `없음`."""
    await _ledger(factory, label_text="원재료명 : 정제수 보관방법 : 실온")

    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)
    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)

    async with factory() as session:
        label = (await session.execute(select(FoodLabel))).scalar_one()
        assert label.allergen_declaration == "unknown"


@pytest.mark.asyncio
async def test_a_product_declared_many_times_has_one_printed_label(factory, pinned) -> None:
    """3.6 declarations per product, 1,226 at the widest - and one label (2026-09-14).

    The label read is the newest 처리일자 that printed one: a declaration with an
    empty paragraph is not the product's label however new it is, which is
    10,153 of the 1,055,682 declarations.
    """
    await _ledger(factory, label_text=PRINTED)
    await _declaration(
        factory,
        label_text=PRINTED.replace("정제소금", "천일염"),
        processed_date="20261001",
    )
    # Declared twice on one day: the tie keeps what is already held, so a
    # product never mixes two paragraphs.
    await _declaration(
        factory,
        label_text=PRINTED.replace("정제소금", "히말라야소금"),
        processed_date="20261001",
        expiry="20261001 ~ 20290101",
    )
    await _declaration(factory, label_text=None, processed_date="20261101")

    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)

    async with factory() as session:
        label = (await session.execute(select(FoodLabel))).scalar_one()
        assert label.raw_material_text == "돼지고기, 유당(우유), 천일염"

    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)
    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)
    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)

    async with factory() as session:
        for model in (FoodLabelAllergen, FoodLabelCaution, FoodLabelPackaging):
            rows = (await session.execute(select(model))).scalars().all()
            assert {row.label_key for row in rows} == {label.label_key}, model
