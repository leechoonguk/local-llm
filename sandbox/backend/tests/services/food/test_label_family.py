"""FoodLabelFamilyService tests - one printed label and the three lists on it.

The family is written by one derivation (one scan of each ledger, one parse of
each paragraph), so a rebuild returns the rows of all four tables and every
assertion below counts the table it is about.
"""

import pytest
from sqlalchemy import select

from app.models.food.label import FoodLabel
from app.models.food.label_allergen import FoodLabelAllergen
from app.models.food.label_caution import FoodLabelCaution
from app.models.food.label_packaging import FoodLabelPackaging
from app.models.food.ledger_haccp_label import FoodLedgerHaccpLabel
from app.models.food.ledger_qr_allergy import FoodLedgerQrAllergy
from app.models.food.ledger_qr_caution import FoodLedgerQrCaution
from app.models.food.ledger_qr_label import FoodLedgerQrLabel
from app.models.food.ledger_qr_manufacture import FoodLedgerQrManufacture
from app.models.food.ledger_qr_nutrition import FoodLedgerQrNutrition
from app.models.food.ledger_qr_packaging import FoodLedgerQrPackaging
from app.models.food.ledger_qr_raw_material import FoodLedgerQrRawMaterial
from app.models.food.ledger_qr_storage import FoodLedgerQrStorage
from app.services.food.label_family import FoodLabelFamilyService


SYNCED_BY = "batch:derive_food_tables"


@pytest.mark.asyncio
async def test_rebuild_assembles_a_qr_label_from_its_five_feeds(factory, pinned) -> None:
    """A 푸드QR label is its 표시사항 row plus what the sibling feeds say about it."""
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerQrLabel(
                    label_no="L1",
                    product_name="전복삼계죽 420g",
                    barcode_no="08801007901244",
                    food_type_name="즉석조리식품",
                    content_amount_text="420g (215kcal)",
                    refrigerated_yn="N",
                ),
                FoodLedgerQrStorage(
                    label_no="L1",
                    detail_serial="1",
                    storage_text="직사광선을피한실온에보관하십시오.",
                ),
                # A row whose text is markup and nothing else says nothing; it must
                # not overwrite the line above it with an empty string.
                FoodLedgerQrStorage(label_no="L1", detail_serial="2", storage_text="<p></p>"),
                FoodLedgerQrRawMaterial(
                    label_no="L1",
                    raw_material_serial="1",
                    raw_material_html=(
                        '<a href="x"><span>정제수</span></a>, <a><span>멥쌀(<p>국산</p>)</span></a>'
                    ),
                ),
                FoodLedgerQrManufacture(
                    label_no="L1",
                    item_report_serial="1",
                    item_report_no="20190450208110",
                    business_name="씨제이제일제당(주)",
                    representative_name="강*호",
                    site_address="충청북도 진천군",
                ),
                FoodLedgerQrNutrition(
                    label_no="L1", nutrition_detail_serial="1", item_report_no="20190450208110"
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodLabelFamilyService(session)
        assert await service.rebuild_label_family(SYNCED_BY) == 1
        assert await service.rebuild_label_family(SYNCED_BY) == 1

    async with factory() as session:
        (row,) = (await session.execute(select(FoodLabel))).scalars().all()
    assert (row.source, row.label_key) == ("food-qr", "L1")
    assert row.item_report_no == "20190450208110"
    assert row.storage_text == "직사광선을피한실온에보관하십시오."
    # The 원재료 feed answers HTML; what lands is the sentence a reader sees.
    assert row.raw_material_text == "정제수, 멥쌀(국산)"
    assert row.business_name == "씨제이제일제당(주)"
    assert row.representative_name == "강*호"
    assert row.site_address == "충청북도 진천군"
    assert row.created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_rebuild_keeps_the_two_portals_labels_apart(factory, pinned) -> None:
    """One 품목보고번호 with a label in each portal is two rows, not a merge.

    Measured 2026-09-13 on the 56 보고 both feeds carry: 내용량 agrees on 11 of
    them, because the portals hold different packages of the same report.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerQrLabel(
                    label_no="L1", product_name="밀키스", content_amount_text="250mL"
                ),
                FoodLedgerQrNutrition(
                    label_no="L1", nutrition_detail_serial="1", item_report_no="1978036800228"
                ),
                FoodLedgerHaccpLabel(
                    item_report_no="1978036800228",
                    product_name="밀키스",
                    capacity_text="250ml*6",
                    maker_name="롯데칠성음료",
                    raw_material_names="정제수,설탕",
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)

    async with factory() as session:
        rows = (await session.execute(select(FoodLabel).order_by(FoodLabel.source))).scalars().all()
    assert [(r.source, r.label_key, r.content_amount_text) for r in rows] == [
        ("food-qr", "L1", "250mL"),
        ("haccp", "1978036800228", "250ml*6"),
    ]
    # Both point at the same report, which is what the screen joins them by.
    assert {r.item_report_no for r in rows} == {"1978036800228"}
    # The HACCP portal publishes no 유효기간 and no 여부 flags; a NULL says so.
    assert rows[1].valid_from is None and rows[1].refrigerated_yn is None
    assert rows[1].raw_material_text == "정제수,설탕"


@pytest.mark.asyncio
async def test_rebuild_tells_an_unknown_declaration_from_an_empty_one(factory, pinned) -> None:
    """A publisher that wrote 알수없음 has not said the package is allergen-free.

    Measured 2026-09-13: 8,479 of the HACCP feed's 14,664 rows read that word and
    41 read 없음, and 새우탕큰사발면 declares twelve substances on its 푸드QR label
    against 알수없음 on its HACCP one.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerQrLabel(label_no="L1", product_name="새우탕큰사발면"),
                FoodLedgerQrAllergy(label_no="L1", allergen_serial="1", allergen_name="새우"),
                FoodLedgerQrLabel(label_no="L2", product_name="알레르기 피드에 없는 라벨"),
                FoodLedgerHaccpLabel(item_report_no="R1", allergy_names="알수없음"),
                FoodLedgerHaccpLabel(item_report_no="R2", allergy_names="없음"),
                FoodLedgerHaccpLabel(item_report_no="R3", allergy_names="새우,대두"),
                FoodLedgerHaccpLabel(item_report_no="R4", allergy_names=None),
            ]
        )
        await session.commit()

    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodLabel).order_by(FoodLabel.source, FoodLabel.label_key)
                )
            )
            .scalars()
            .all()
        )
    assert [(r.label_key, r.allergen_declaration) for r in rows] == [
        ("L1", "declared"),
        # The 알레르기 feed knows 1,746 of the 2,276 labels, so silence is unknown.
        ("L2", "unknown"),
        ("R1", "unknown"),
        ("R2", "none"),
        ("R3", "declared"),
        ("R4", "unknown"),
    ]


@pytest.mark.asyncio
async def test_rebuild_numbers_each_labels_allergens_and_drops_repeats(factory, pinned) -> None:
    """One row per declaration, and a name repeated across 표시그룹 is one row here."""
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerQrAllergy(label_no="L1", allergen_serial="1", allergen_name="밀"),
                FoodLedgerQrAllergy(label_no="L1", allergen_serial="2", allergen_name="우유"),
                FoodLedgerQrAllergy(label_no="L1", allergen_serial="3", allergen_name="밀"),
                FoodLedgerQrAllergy(
                    label_no="L2", allergen_serial="4", allergen_name="조개류(굴, 가리비)"
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodLabelFamilyService(session)
        assert await service.rebuild_label_family(SYNCED_BY) == 3
        assert await service.rebuild_label_family(SYNCED_BY) == 3

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodLabelAllergen).order_by(
                        FoodLabelAllergen.label_key, FoodLabelAllergen.position
                    )
                )
            )
            .scalars()
            .all()
        )
    assert [(r.source, r.label_key, r.position, r.name) for r in rows] == [
        ("food-qr", "L1", 1, "밀"),
        ("food-qr", "L1", 2, "우유"),
        ("food-qr", "L2", 1, "조개류(굴, 가리비)"),
    ]


@pytest.mark.asyncio
async def test_rebuild_splits_the_haccp_string_and_refuses_what_is_not_a_declaration(
    factory,
    pinned,
) -> None:
    """A publisher writing 알수없음 has declared nothing, so nothing is stored.

    Measured 2026-09-13: 8,484 of the HACCP feed's 14,664 values read that word,
    and 41 read 없음.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerHaccpLabel(item_report_no="R1", allergy_names="우유 함유,대두,밀"),
                FoodLedgerHaccpLabel(item_report_no="R2", allergy_names="알수없음"),
                FoodLedgerHaccpLabel(item_report_no="R3", allergy_names="없음"),
                FoodLedgerHaccpLabel(item_report_no="R4", allergy_names="조개류(굴"),
                # A stray closing bracket is the mirror of the case above.
                FoodLedgerHaccpLabel(item_report_no="R6", allergy_names="조개류)굴"),
                FoodLedgerHaccpLabel(item_report_no="R5", allergy_names=None),
            ]
        )
        await session.commit()

    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodLabelAllergen).order_by(
                        FoodLabelAllergen.label_key, FoodLabelAllergen.position
                    )
                )
            )
            .scalars()
            .all()
        )
    assert [(r.label_key, r.position, r.name) for r in rows] == [
        ("R1", 1, "우유"),
        ("R1", 2, "대두"),
        ("R1", 3, "밀"),
        # A split that landed inside a bracket is cut back, never stored unbalanced.
        ("R4", 1, "조개류"),
        ("R6", 1, "조개류"),
    ]
    assert {r.source for r in rows} == {"haccp"}


@pytest.mark.asyncio
async def test_rebuild_numbers_each_labels_cautions_in_printed_order(factory, pinned) -> None:
    """One row per printed entry, numbered from 1 within its label."""
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerQrCaution(label_no="L1", detail_serial="2", caution_text="두 번째"),
                FoodLedgerQrCaution(label_no="L1", detail_serial="1", caution_text="첫 번째"),
                FoodLedgerQrCaution(label_no="L2", detail_serial="1", caution_text="다른 라벨"),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodLabelFamilyService(session)
        assert await service.rebuild_label_family(SYNCED_BY) == 3
        assert await service.rebuild_label_family(SYNCED_BY) == 3

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodLabelCaution).order_by(
                        FoodLabelCaution.label_key, FoodLabelCaution.position
                    )
                )
            )
            .scalars()
            .all()
        )
    assert [(r.source, r.label_key, r.position, r.caution_text) for r in rows] == [
        ("food-qr", "L1", 1, "첫 번째"),
        ("food-qr", "L1", 2, "두 번째"),
        ("food-qr", "L2", 1, "다른 라벨"),
    ]


@pytest.mark.asyncio
async def test_rebuild_stages_more_caution_rows_than_one_page_holds(
    factory, pinned, monkeypatch
) -> None:
    """The ledger is staged in pages, so a feed wider than one page still lands whole."""
    monkeypatch.setattr("app.services.food.label_family.PAGE_SIZE", 2)
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerQrCaution(label_no="L1", detail_serial=f"{index}", caution_text="문구")
                for index in range(1, 6)
            ]
        )
        await session.commit()

    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)

    async with factory() as session:
        rows = (
            (await session.execute(select(FoodLabelCaution).order_by(FoodLabelCaution.position)))
            .scalars()
            .all()
        )
    assert [row.position for row in rows] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_rebuild_numbers_each_labels_packaging_parts_in_printed_order(
    factory, pinned
) -> None:
    """One row per printed entry, numbered from 1 within its label."""
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerQrPackaging(
                    label_no="L1",
                    detail_serial="2",
                    item_report_serial="1",
                    packaging_text="두 번째",
                ),
                FoodLedgerQrPackaging(
                    label_no="L1",
                    detail_serial="1",
                    item_report_serial="1",
                    packaging_text="첫 번째",
                ),
                FoodLedgerQrPackaging(
                    label_no="L2",
                    detail_serial="1",
                    item_report_serial="1",
                    packaging_text="다른 라벨",
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodLabelFamilyService(session)
        assert await service.rebuild_label_family(SYNCED_BY) == 3
        assert await service.rebuild_label_family(SYNCED_BY) == 3

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodLabelPackaging).order_by(
                        FoodLabelPackaging.label_key, FoodLabelPackaging.position
                    )
                )
            )
            .scalars()
            .all()
        )
    assert [(r.source, r.label_key, r.position, r.packaging_text) for r in rows] == [
        ("food-qr", "L1", 1, "첫 번째"),
        ("food-qr", "L1", 2, "두 번째"),
        ("food-qr", "L2", 1, "다른 라벨"),
    ]


@pytest.mark.asyncio
async def test_rebuild_stages_more_packaging_rows_than_one_page_holds(
    factory, pinned, monkeypatch
) -> None:
    """The ledger is staged in pages, so a feed wider than one page still lands whole."""
    monkeypatch.setattr("app.services.food.label_family.PAGE_SIZE", 2)
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerQrPackaging(
                    label_no="L1",
                    detail_serial=f"{index}",
                    item_report_serial="1",
                    packaging_text="문구",
                )
                for index in range(1, 6)
            ]
        )
        await session.commit()

    async with pinned() as session:
        await FoodLabelFamilyService(session).rebuild_label_family(SYNCED_BY)

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodLabelPackaging).order_by(FoodLabelPackaging.position)
                )
            )
            .scalars()
            .all()
        )
    assert [row.position for row in rows] == [1, 2, 3, 4, 5]
