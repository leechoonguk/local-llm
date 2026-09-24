"""FoodRawMaterialService tests — the rebuild off I2520, and the reads over what it wrote."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.models.food.ledger_raw_material import FoodLedgerRawMaterial
from app.models.food.raw_material import FoodRawMaterial
from app.schemas.food.raw_material import FoodRawMaterialFilter
from app.services.food.raw_material import FoodRawMaterialService


SYNCED_BY = "batch:derive_food_tables"


def _code(code: str, name: str, **overrides: object) -> FoodLedgerRawMaterial:
    """One ledger code, in use unless said otherwise."""
    fields: dict[str, object] = {"use_yn": "Y", "raw_material_large_class": "식품원료(A코드)"}
    fields.update(overrides)
    return FoodLedgerRawMaterial(
        raw_material_code=code, representative_raw_material_name=name, **fields
    )


@pytest.mark.asyncio
async def test_rebuild_writes_what_food_is_made_of_with_its_base_code(factory, pinned) -> None:
    """The derived table is the ledger minus 기구·용기포장 and 위생용품, each code with its base.

    A retired code stays - it is what an old report meant by the name - and
    two variants of one material (밀가루 whole/powder, 밀기울 bran) share one
    `base_code`, the first eight characters.
    """
    async with factory() as session:
        session.add_all(
            [
                _code("A1000911010001", "밀가루"),
                _code("A1000911280000", "밀기울", use_yn="N"),
                _code("E0000100000000", "폴리에틸렌", raw_material_large_class="위생용품(E코드)"),
                _code("D0000100000000", "유리", raw_material_large_class="기구 및 용기포장(D코드)"),
            ]
        )
        await session.commit()

    async with pinned() as session:
        assert await FoodRawMaterialService(session).rebuild_raw_material(SYNCED_BY) == 2

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodRawMaterial).order_by(FoodRawMaterial.raw_material_code)
                )
            )
            .scalars()
            .all()
        )
    kept = [(r.raw_material_code, r.base_code, r.representative_raw_material_name) for r in rows]
    assert kept == [
        ("A1000911010001", "A1000911", "밀가루"),
        ("A1000911280000", "A1000911", "밀기울"),
    ]


def _material(code: str, name: str, **overrides: object) -> FoodRawMaterial:
    """One derived row, the way the rebuild leaves it."""
    fields: dict[str, object] = {
        "use_yn": "Y",
        "raw_material_large_class": "식품원료(A코드)",
        "raw_material_medium_class": "식물",
        "raw_material_status_code_name": "가루",
    }
    fields.update(overrides)
    return FoodRawMaterial(
        raw_material_code=code, base_code=code[:8], representative_raw_material_name=name, **fields
    )


@pytest.mark.asyncio
async def test_list_and_count_narrow_together_by_fragment_and_by_whole_value(factory) -> None:
    """Free text matches a fragment, a class matches whole; the total counts the same filter."""
    async with factory() as session:
        session.add_all(
            [
                _material("A1000911010001", "밀가루"),
                _material("A1000911280000", "밀기울", raw_material_status_code_name="껍질"),
                _material("A1000912010001", "밀배아", raw_material_medium_class="식물성유지"),
                _material("B0100010000000", "구연산", raw_material_large_class="식품첨가물(B코드)"),
            ]
        )
        await session.commit()

    async with factory() as session:
        service = FoodRawMaterialService(session)
        by_name = FoodRawMaterialFilter(representative_raw_material_name="밀")
        assert [r.raw_material_code for r in await service.list_raw_materials(0, 2, by_name)] == [
            "A1000911010001",
            "A1000911280000",
        ]
        assert await service.count_raw_materials(by_name) == 3
        # Whole-value: 식물 does not reach 식물성유지, so 밀배아 is out and the other three in.
        whole = FoodRawMaterialFilter(raw_material_medium_class="식물")
        assert await service.count_raw_materials(whole) == 3
        assert await service.count_raw_materials(None) == 4


@pytest.mark.asyncio
async def test_facets_are_the_rows_own_values_with_the_medium_class_under_its_large(
    factory,
) -> None:
    """A select offers what a row can match: sorted, NULL left out, the child grouped by parent."""
    async with factory() as session:
        session.add_all(
            [
                _material("A1000911010001", "밀가루"),
                _material("A1000912010001", "밀배아", raw_material_medium_class="식물성유지"),
                _material(
                    "B0100010000000",
                    "구연산",
                    raw_material_large_class="식품첨가물(B코드)",
                    raw_material_medium_class=None,
                    raw_material_status_code_name=None,
                ),
            ]
        )
        await session.commit()

    async with factory() as session:
        facets = await FoodRawMaterialService(session).list_raw_material_facets()
    assert facets.raw_material_large_class == ["식품원료(A코드)", "식품첨가물(B코드)"]
    assert facets.raw_material_medium_class == ["식물", "식물성유지"]
    assert facets.raw_material_medium_class_by_large == {"식품원료(A코드)": ["식물", "식물성유지"]}
    assert facets.raw_material_status_code_name == ["가루"]


@pytest.mark.asyncio
async def test_get_loads_the_base_variants_and_a_missing_id_is_not_found(factory) -> None:
    """One material comes with every code of its base, itself included, in code order."""
    async with factory() as session:
        session.add_all(
            [
                _material("A1000911280000", "밀기울"),
                _material("A1000911010001", "밀가루"),
                _material("A1000912010001", "밀배아"),
            ]
        )
        await session.commit()
        stored = await session.scalar(
            select(FoodRawMaterial).where(FoodRawMaterial.raw_material_code == "A1000911280000")
        )
        assert stored is not None

    async with factory() as session:
        service = FoodRawMaterialService(session)
        material = await service.get_raw_material(stored.id)
        assert [v.raw_material_code for v in material.variants] == [
            "A1000911010001",
            "A1000911280000",
        ]
        with pytest.raises(NotFoundError):
            await service.get_raw_material(uuid4())
