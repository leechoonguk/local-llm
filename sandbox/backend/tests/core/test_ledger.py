"""LedgerStage: a whole pass in a TEMP table, written over its ledger as a set.

The contract under test is what a ledger looks like after a pass - equal to
the pass, every row the pass's, with the id a record keeps from one pass to
the next - and what the stage refuses: a pass too small to be believed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import LedgerFloorError
from app.core.ledger import LedgerStage, scan_table
from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial as FoodLivestock,
)
from app.schemas.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterialCreateRequest,
)
from app.services.food.ledger_livestock_item_report_raw_material import NATURAL_KEY, SYNCED_COLUMNS


def _row(item_report_no: str, product_name: str = "닭꼬치", changed: str = "") -> dict[str, object]:
    """A staged row in the ledger's own column names, as the service builds it."""
    request = FoodLedgerLivestockItemReportRawMaterialCreateRequest.from_record(
        {"item_report_no": item_report_no, "product_name": product_name, "changed_date": changed}
    )
    assert request is not None
    return request.model_dump()


@asynccontextmanager
async def _pinned(engine) -> AsyncIterator[AsyncSession]:
    async with (
        engine.connect() as connection,
        AsyncSession(connection, expire_on_commit=False) as session,
    ):
        yield session


async def _replace(
    session: AsyncSession, *pages: list[dict[str, object]], actor: str, newest: str | None = None
) -> int:
    """One pass: create, stage every page, replace, drop - the service's own sequence."""
    stage = LedgerStage(session, FoodLivestock, NATURAL_KEY, SYNCED_COLUMNS, newest=newest)
    async with session.begin():
        await stage.create()
    for page in pages:
        async with session.begin():
            await stage.add(page)
    async with session.begin():
        written = await stage.replace(actor)
    async with session.begin():
        await stage.drop()
    return written


async def _ledger(session: AsyncSession) -> dict[str, FoodLivestock]:
    async with session.begin():
        rows = (await session.execute(select(FoodLivestock))).scalars().all()
        return {row.item_report_no: row for row in rows}


@pytest.mark.asyncio
async def test_the_ledger_after_a_pass_is_the_pass(engine) -> None:
    """Every row is the pass's - gone, changed, re-sent or new alike - under the same id."""
    async with _pinned(engine) as session:
        assert await _replace(session, [_row("A"), _row("B"), _row("C")], actor="night-1") == 3
        before = await _ledger(session)
        ids = {name: row.id for name, row in before.items()}
        assert {row.version for row in before.values()} == {1}
        assert {row.created_by for row in before.values()} == {"night-1"}

    async with _pinned(engine) as session:
        # A unchanged, B changed, C gone, D new.
        assert (
            await _replace(session, [_row("A"), _row("B", "닭날개"), _row("D")], actor="night-2")
            == 3
        )
        after = await _ledger(session)
        assert set(after) == {"A", "B", "D"}
        assert {row.version for row in after.values()} == {1}
        assert {row.created_by for row in after.values()} == {"night-2"}
        assert {row.updated_by for row in after.values()} == {"night-2"}
        assert after["B"].product_name == "닭날개"
        # The id is the record's, not the night's: minted from the natural key.
        assert after["A"].id == ids["A"] and after["B"].id == ids["B"]
        assert after["D"].id not in ids.values()


def test_a_row_id_is_the_natural_key_and_nothing_else() -> None:
    """The same key gives the same id on any host; a different table or key does not."""
    stage = LedgerStage.__new__(LedgerStage)
    stage.live = FoodLivestock.__table__  # type: ignore[assignment]
    stage.natural_key = ("item_report_no",)
    assert stage._row_id({"item_report_no": "A"}) == stage._row_id({"item_report_no": "A"})
    assert stage._row_id({"item_report_no": "A"}) != stage._row_id({"item_report_no": "B"})
    stage.natural_key = ("a", "b")
    # Unit-separated, so ("ab", "c") is not ("a", "bc").
    assert stage._row_id({"a": "ab", "b": "c"}) != stage._row_id({"a": "a", "b": "bc"})


@pytest.mark.asyncio
async def test_a_key_the_pass_already_staged_is_skipped(engine) -> None:
    """The provider re-sends across windows; the first reading stands."""
    async with _pinned(engine) as session:
        written = await _replace(
            session, [_row("A", "first"), _row("A", "again")], [_row("A", "later")], actor="t"
        )
        assert written == 1
        assert (await _ledger(session))["A"].product_name == "first"


@pytest.mark.asyncio
async def test_with_a_newest_column_the_latest_reading_stands(engine) -> None:
    """A feed that sends every revision of a record: the greatest stamp wins, in a page or across.

    A reading with no stamp loses to any stamped one and never displaces one
    (in the page: A's second reading; across pages: B's third), and two
    stampless readings keep the first (C).
    """
    async with _pinned(engine) as session:
        written = await _replace(
            session,
            [
                _row("A", "old", "20161023"),
                _row("A", "new", "20231016"),
                _row("A", "unstamped"),
                _row("A", "older", "20191202"),
                _row("B", "unstamped"),
                _row("B", "stamped", "20200101"),
                _row("C", "first"),
                _row("C", "second"),
            ],
            [_row("A", "late-older", "20200101"), _row("B", "late-unstamped")],
            [_row("B", "late-newer", "20210101"), _row("C", "late-unstamped")],
            actor="t",
            newest="source_updated_at",
        )
        assert written == 3
        ledger = await _ledger(session)
        assert {name: row.product_name for name, row in ledger.items()} == {
            "A": "new",
            "B": "late-newer",
            "C": "first",
        }


@pytest.mark.asyncio
async def test_a_table_scans_back_in_key_order_by_pages(engine) -> None:
    """`scan_table` hands a table's rows back once each, ordered by key, whatever the page size."""
    async with _pinned(engine) as session:
        rows = [_row("C"), _row("A"), _row("E"), _row("B"), _row("D")]
        await _replace(session, rows, actor="pass")
        pages = [
            [row["item_report_no"] for row in page]
            async for page in scan_table(session, FoodLivestock, NATURAL_KEY, SYNCED_COLUMNS, 2)
        ]
        assert pages == [["A", "B"], ["C", "D"], ["E"]]
        assert [
            len(page)
            async for page in scan_table(session, FoodLivestock, NATURAL_KEY, SYNCED_COLUMNS, 5)
        ] == [5]


@pytest.mark.asyncio
async def test_a_pass_under_the_floor_leaves_the_ledger_untouched(engine) -> None:
    """A feed that lost half its rows overnight is a provider's bad night, not news."""
    async with _pinned(engine) as session:
        await _replace(session, [_row("A"), _row("B"), _row("C"), _row("D")], actor="t")

    async with _pinned(engine) as session:
        stage = LedgerStage(session, FoodLivestock, NATURAL_KEY, SYNCED_COLUMNS)
        async with session.begin():
            await stage.create()
            await stage.add([_row("A")])
        with pytest.raises(LedgerFloorError, match="staged 1 rows against 4 live") as raised:
            async with session.begin():
                await stage.replace("t")
        assert (raised.value.staged, raised.value.live) == (1, 4)
        assert set(await _ledger(session)) == {"A", "B", "C", "D"}
        # The floor is the caller's to lower: a pass a reader vouches for goes in.
        async with session.begin():
            assert await stage.replace("t", floor=0) == 1
        assert set(await _ledger(session)) == {"A"}


@pytest.mark.asyncio
async def test_an_empty_ledger_has_no_floor(engine) -> None:
    """The first load has nothing to compare against and must not be refused."""
    async with _pinned(engine) as session:
        assert await _replace(session, [_row("A")], actor="t") == 1


@pytest.mark.asyncio
async def test_an_empty_pass_is_refused_even_into_an_empty_ledger(engine) -> None:
    """A feed that answered nothing is a window past the ceiling, not a first load."""
    async with _pinned(engine) as session:
        with pytest.raises(LedgerFloorError, match="staged 0 rows against 0 live"):
            await _replace(session, [], actor="t")
        assert await _ledger(session) == {}


@pytest.mark.asyncio
async def test_create_starts_empty_whatever_the_connection_holds(engine) -> None:
    """A pass that died mid-way leaves its stage on the pooled connection."""
    async with _pinned(engine) as session:
        stage = LedgerStage(session, FoodLivestock, NATURAL_KEY, SYNCED_COLUMNS)
        async with session.begin():
            await stage.create()
            await stage.add([_row("A"), _row("B")])
        # The next pass on the same connection, without a drop in between.
        async with session.begin():
            await stage.create()
            assert await stage.count() == (0, 0)
