"""FoodStandardService tests — the rebuild off both 공전 ledgers, and the clause's edges."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.food.common_standard_type import FoodCommonStandardType
from app.models.food.ledger_common_standard import FoodLedgerCommonStandard
from app.models.food.ledger_individual_standard import FoodLedgerIndividualStandard
from app.models.food.product_classification import FoodProductClassification
from app.models.food.standard import FoodStandard
from app.models.food.test_item import FoodTestItem
from app.services.food.standard import FoodStandardService


SYNCED_BY = "batch:derive_food_tables"


def _node(code: str, name: str, root: str) -> FoodProductClassification:
    return FoodProductClassification(
        product_code=code, korean_name=name, product_yn="Y", root_product_code=root
    )


def _clause(kind: str, seq: str, product_code: str, item: str = "C20001") -> FoodStandard:
    return FoodStandard(
        standard_kind=kind,
        standard_seq=seq,
        test_item_code=item,
        product_code=product_code,
        common_standard_type_code="000140" if kind == "common" else None,
    )


@pytest.mark.asyncio
async def test_rebuild_writes_both_chapters_under_their_kind(factory, pinned) -> None:
    """Each ledger lands under its own kind, and a rerun replaces rather than doubles.

    The two registries number in their own spaces, so the same serial can name a
    제2 clause and a 제5 one: they are two rows, told apart by the kind alone.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerCommonStandard(
                    common_standard_seq="1", test_item_code="C20001", product_code="A1000911000000"
                ),
                FoodLedgerCommonStandard(
                    common_standard_seq="2", test_item_code="C20001", product_code="X0100028700000"
                ),
                FoodLedgerIndividualStandard(
                    individual_standard_seq="1",
                    test_item_code="C20001",
                    detail_item_name="총 아플라톡신",
                    clause_seq="1",
                    product_code="C0301040000000",
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodStandardService(session)
        assert await service.rebuild_standard(SYNCED_BY) == 3
        assert await service.rebuild_standard(SYNCED_BY) == 3

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodStandard).order_by(
                        FoodStandard.standard_kind, FoodStandard.standard_seq
                    )
                )
            )
            .scalars()
            .all()
        )
    assert [
        (r.standard_kind, r.standard_seq, r.product_code, r.detail_item_name, r.clause_seq)
        for r in rows
    ] == [
        ("common", "1", "A1000911000000", "", ""),
        ("common", "2", "X0100028700000", "", ""),
        ("individual", "1", "C0301040000000", "총 아플라톡신", "1"),
    ]


@pytest.mark.asyncio
async def test_a_clause_names_its_node_heading_and_item(factory) -> None:
    """A clause points at the node it is written on, the 공전 heading, and the test item.

    The heading is 제2's alone — a 개별 clause hangs under none, and the edge
    answers None rather than borrowing the sibling chapter's.
    """
    async with factory() as session:
        session.add_all(
            [
                _node("B01010100F2000", "소유", "B0000000000000"),
                FoodCommonStandardType(
                    common_standard_type_code="000140", standard_name="(2) 별표 5"
                ),
                FoodTestItem(test_item_code="C20001", korean_name="설파메타진"),
                _clause("common", "1", "B01010100F2000"),
                _clause("common", "2", "X0100028700000", item="C29999"),
                _clause("individual", "3", "B01010100F2000"),
            ]
        )
        await session.commit()

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodStandard)
                    .options(
                        joinedload(FoodStandard.classification),
                        joinedload(FoodStandard.standard_type),
                        joinedload(FoodStandard.test_item),
                    )
                    .order_by(FoodStandard.standard_seq)
                )
            )
            .scalars()
            .all()
        )

    assert [
        (
            r.classification and r.classification.korean_name,
            r.standard_type and r.standard_type.standard_name,
            r.test_item and r.test_item.korean_name,
        )
        for r in rows
    ] == [
        ("소유", "(2) 별표 5", "설파메타진"),
        (None, "(2) 별표 5", None),
        ("소유", None, "설파메타진"),
    ]
