"""FoodProductClassificationService tests — the rebuild off I2510, and the report edge."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.food.item_report import FoodItemReport
from app.models.food.ledger_product_classification import FoodLedgerProductClassification
from app.models.food.product_classification import FoodProductClassification
from app.services.food.product_classification import FoodProductClassificationService


SYNCED_BY = "batch:derive_food_tables"


def _node(code: str, name: str, **overrides: object) -> FoodLedgerProductClassification:
    """One ledger node: a live type unless said otherwise."""
    fields: dict[str, object] = {"product_yn": "Y", "valid_end_date": "99991231", "level": "5"}
    fields.update(overrides)
    return FoodLedgerProductClassification(product_code=code, korean_name=name, **fields)


@pytest.mark.asyncio
async def test_rebuild_writes_the_tree_as_it_stands_tiers_included(factory, pinned) -> None:
    """The derived table is the ledger minus the retired nodes and the Z root - and keeps the tiers.

    A tier (`product_yn` = `N`) is a row because a 공통기준규격 hangs on one; a
    retired node and a Z node are not, because their names are the living
    tree's names and a join on a name would find both. Run twice, the table
    is the second run: a rebuild replaces, it does not accumulate.
    """
    async with factory() as session:
        session.add_all(
            [
                _node("C0301040000000", "빵류"),
                _node("C0301000000000", "과자류", product_yn="N", level="4"),
                _node("C0102010000000", "빵류", valid_end_date="20171231"),
                _node("Z2900500000000", "절임식품"),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodProductClassificationService(session)
        assert await service.rebuild_product_classification(SYNCED_BY) == 2
        assert await service.rebuild_product_classification(SYNCED_BY) == 2

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodProductClassification).order_by(
                        FoodProductClassification.product_code
                    )
                )
            )
            .scalars()
            .all()
        )
    assert [(r.product_code, r.korean_name, r.product_yn, r.created_by) for r in rows] == [
        ("C0301000000000", "과자류", "N", SYNCED_BY),
        ("C0301040000000", "빵류", "Y", SYNCED_BY),
    ]


@pytest.mark.asyncio
async def test_report_type_name_resolves_to_the_types_of_that_name(factory) -> None:
    """A 식품유형명 lists every *type* of that name; a same-named tier and a misspelling do not."""
    async with factory() as session:
        session.add_all(
            [
                FoodProductClassification(product_code="D0801", korean_name="향료", product_yn="Y"),
                FoodProductClassification(product_code="D0844", korean_name="향료", product_yn="Y"),
                FoodProductClassification(product_code="D0600", korean_name="향료", product_yn="N"),
                FoodProductClassification(product_code="C0301", korean_name="빵류", product_yn="Y"),
                FoodItemReport(
                    report_kind="domestic", item_report_no="1", product_type_name="향료"
                ),
                FoodItemReport(
                    report_kind="livestock", item_report_no="1", product_type_name="향 료"
                ),
            ]
        )
        await session.commit()

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodItemReport)
                    .options(joinedload(FoodItemReport.product_classifications))
                    .order_by(FoodItemReport.report_kind)
                )
            )
            .unique()
            .scalars()
            .all()
        )

    assert [sorted(c.product_code for c in r.product_classifications) for r in rows] == [
        ["D0801", "D0844"],
        [],
    ]
