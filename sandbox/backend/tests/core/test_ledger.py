"""LedgerStage: a whole pass in a TEMP table, merged into its ledger as a set.

The contract under test is what a ledger looks like after a pass - equal to
the pass, with the rows it kept still carrying their id, and the rows it
changed carrying the next version - and what the stage refuses: a pass too
small to be believed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import LedgerFloorError
from app.core.ledger import LedgerStage
from app.models.food.barcode import FoodBarcode
from app.schemas.food.barcode import FoodBarcodeCreateRequest
from app.services.food.barcode import NATURAL_KEY, SYNCED_COLUMNS


REPORT_NO = "F2024000123456"


def _row(barcode_no: str, product_name: str = "김치") -> dict[str, object]:
    """A staged row in the ledger's own column names, as the service builds it."""
    request = FoodBarcodeCreateRequest.from_record(
        {"barcode_no": barcode_no, "report_no": REPORT_NO, "product_name": product_name}
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


async def _replace(session: AsyncSession, *pages: list[dict[str, object]], actor: str) -> int:
    """One pass: create, stage every page, merge, drop - the service's own sequence."""
    stage = LedgerStage(session, FoodBarcode, NATURAL_KEY, SYNCED_COLUMNS)
    async with session.begin():
        await stage.create()
    for page in pages:
        async with session.begin():
            await stage.add(page)
    async with session.begin():
        written = await stage.merge(actor)
    async with session.begin():
        await stage.drop()
    return written


async def _ledger(session: AsyncSession) -> dict[str, FoodBarcode]:
    async with session.begin():
        rows = (await session.execute(select(FoodBarcode))).scalars().all()
        return {row.barcode_no: row for row in rows}


@pytest.mark.asyncio
async def test_the_ledger_after_a_pass_is_the_pass(engine) -> None:
    """Deleted, updated, inserted, left alone - and the survivors keep their id."""
    async with _pinned(engine) as session:
        assert await _replace(session, [_row("A"), _row("B"), _row("C")], actor="night-1") == 3
        before = await _ledger(session)
        ids = {name: row.id for name, row in before.items()}
        assert {row.version for row in before.values()} == {1}
        assert {row.created_by for row in before.values()} == {"night-1"}

    async with _pinned(engine) as session:
        # A unchanged, B changed, C gone, D new.
        assert (
            await _replace(session, [_row("A"), _row("B", "묵은지"), _row("D")], actor="night-2")
            == 3
        )
        after = await _ledger(session)
        assert set(after) == {"A", "B", "D"}
        assert after["A"].id == ids["A"] and after["A"].version == 1
        assert after["A"].updated_by == "night-1"
        assert after["B"].id == ids["B"] and after["B"].version == 2
        assert (after["B"].product_name, after["B"].updated_by) == ("묵은지", "night-2")
        assert after["D"].created_by == "night-2"
        assert after["D"].id not in ids.values()


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
async def test_a_pass_under_the_floor_leaves_the_ledger_untouched(engine) -> None:
    """A feed that lost half its rows overnight is a provider's bad night, not news."""
    async with _pinned(engine) as session:
        await _replace(session, [_row("A"), _row("B"), _row("C"), _row("D")], actor="t")

    async with _pinned(engine) as session:
        stage = LedgerStage(session, FoodBarcode, NATURAL_KEY, SYNCED_COLUMNS)
        async with session.begin():
            await stage.create()
            await stage.add([_row("A")])
        with pytest.raises(LedgerFloorError, match="staged 1 rows against 4 live") as raised:
            async with session.begin():
                await stage.merge("t")
        assert (raised.value.staged, raised.value.live) == (1, 4)
        assert set(await _ledger(session)) == {"A", "B", "C", "D"}
        # The floor is the caller's to lower: a pass a reader vouches for goes in.
        async with session.begin():
            assert await stage.merge("t", floor=0) == 3
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
        stage = LedgerStage(session, FoodBarcode, NATURAL_KEY, SYNCED_COLUMNS)
        async with session.begin():
            await stage.create()
            await stage.add([_row("A"), _row("B")])
        # The next pass on the same connection, without a drop in between.
        async with session.begin():
            await stage.create()
            assert await stage.count() == (0, 0)
