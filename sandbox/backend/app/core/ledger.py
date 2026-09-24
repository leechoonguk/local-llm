# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from typing import Any, NamedTuple, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import (
    Column,
    CursorResult,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    delete,
    func,
    insert,
    literal,
    select,
    text,
    tuple_,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateTable, DropTable
from sqlalchemy.sql import ColumnElement

from app.core.exceptions import LedgerFloorError
from app.models.base import Base


# ============================================================
# Constants
# ============================================================

# Below this share of the live rows a pass is refused as a replacement. Half,
# because a feed that genuinely halved overnight is news an operator should
# hear about before the ledger reflects it, and a pass that lost more than
# that is far more likely a provider answering empty pages than a feed
# shrinking (`LedgerFloorError`).
DEFAULT_FLOOR = 0.5

# The columns `AuditMixin` writes on every table - a pass sets them itself
# (`replace` stamps the actor, the database the times), never from a record.
AUDIT_COLUMNS = ("created_by", "updated_by", "created_at", "updated_at", "version")


# ============================================================
# Classes
# ============================================================


class Feed(NamedTuple):
    """One operation of a provider and the ledger method that replaces it.

    A provider job is a tuple of these: the walk reads `operation_code`, the
    job builds `service` on the pinned ledger session and hands the pages to
    `replace` (`replace_<table>_ledger`), which answers (received, written).

    Whether the walk is one run of positions over the whole feed or one run per
    coordinate of it is not stated here: that is a fact about the service, and
    it lives with the service's other facts on its `integration_operation` row
    (`segment_key`, `segment_first_year`). Either way the pass stages every page
    before the one replace, so the ledger is the whole feed.
    """

    operation_code: str
    service: Callable[[AsyncSession], Any]
    replace: Callable[..., Awaitable[tuple[int, int]]]


class Derivation(NamedTuple):
    """One derived table and the service method that rebuilds it off the ledgers.

    The derive job is a tuple of these: it builds `service` on a pinned
    session and calls `rebuild` (`rebuild_<table>`), which reads the ledgers
    the table is a function of and answers the rows it now holds.
    """

    service: Callable[[AsyncSession], Any]
    rebuild: Callable[..., Awaitable[int]]


class LedgerStage:
    """A whole pass in a TEMP table, written over its ledger in one transaction.

    A ledger is our copy of a provider's feed, and a pass reads the whole feed
    — so the ledger after a pass *is* the pass, and the ledger is written the
    way it is read: every row deleted, every staged row inserted. Staging
    rather than writing the ledger as pages arrive keeps that true without a
    transaction that spans the walk: pages commit into the stage one by one
    (a pass over a million rows spans hours and quota waits), and the ledger
    changes in one short transaction at the end.

    One mechanism, so one meaning per column: `created_at`/`updated_at` are
    when the pass wrote the ledger, `version` is always 1, `created_by`/
    `updated_by` are the pass's actor. Nothing tells a re-sent row from a
    changed one, and nothing needs to — nothing follows a change column
    (2026-09-07: the three-statement merge that kept `version` honest was
    dropped for this; a derived table built from two ledgers wants the same
    write, and a second way to fill a ledger was one more than the job needs).
    `id` alone is stable: it is minted from the natural key (`uuid5`), so a
    reference from elsewhere finds the same row after every pass.

    A derived table is written the same way, by the job that rebuilds it off
    the ledgers (`derive_food_tables`): read in keyed pages (`scan_table`),
    staged, written over whole. No floor there - the ledgers' own floors
    already vouched for the rows it reads - and no slice: a derived table is a
    function of the ledgers as they stand, and the whole of it is that function.

    A key the pass sends twice is staged once. Which reading stands is the
    stage's `newest` column when it has one — the reading with the greater
    value, because a feed may hand over every revision of a record (C006
    sends one 품목제조번호 under several `CHNG_DT`, the oldest an empty shell
    the newest replaced; measured 2026-09-08: 1,627 repeats in 569,537
    records, 419 with a different 원재료 list) and the ledger wants the
    current one — and the first reading otherwise, since a provider that
    only re-sends across windows hands over the same record both times.

    **The session must be bound to one connection**
    (`AsyncSession(engine.connect())`, as the provider jobs build it). A TEMP
    table lives on the connection that created it; a session bound to an
    engine may check a different one out per transaction, and the stage would
    vanish between two pages with an error naming a table that "does not
    exist" — that error, on the second page of the first pass, is what a
    misbound session looks like.
    """

    def __init__(
        self,
        session: AsyncSession,
        model: type[Base],
        natural_key: Sequence[str],
        columns: Sequence[str],
        *,
        newest: str | None = None,
    ) -> None:
        self.session = session
        self.live: Table = model.__table__  # type: ignore[assignment]
        self.natural_key = tuple(natural_key)
        self.columns = tuple(columns)
        self.newest = newest
        # The staged shape: an id minted here so the insert can copy it, the
        # natural key as primary key (what the dedupe conflicts on),
        # and every column a pass may refresh — typed off the live table so a
        # value the ledger would refuse is refused at staging, page by page.
        self.table = Table(
            f"{self.live.name}_stage",
            MetaData(),
            Column("id", self.live.c["id"].type, nullable=False),
            *(
                Column(name, self.live.c[name].type, nullable=name not in self.natural_key)
                for name in (*self.natural_key, *self.columns)
            ),
            PrimaryKeyConstraint(*self.natural_key),
            prefixes=["TEMPORARY"],
        )

    async def create(self) -> None:
        """Make the stage on this connection, replacing one a failed pass left.

        A TEMP table outlives a rollback and a pooled connection outlives the
        run that used it, so a pass that died after a page can hand the next
        run a stage with rows in it. Dropping first makes every pass start
        empty whichever connection it drew.
        """
        await self.session.execute(DropTable(self.table, if_exists=True))
        await self.session.execute(CreateTable(self.table))

    async def add(self, rows: Sequence[Mapping[str, object]]) -> None:
        """Stage one page; a natural key the pass already staged is staged once.

        Not refused, because the provider repeats itself: a window overlapping
        a row the feed shifted under the walk hands the same record twice, and
        a feed that carries revisions hands every one of them over. The dedupe
        is the database's own conflict clause, so it holds within a page as
        well as across pages: the first reading stands, unless the stage has a
        `newest` column and the later reading is greater on it — then the
        later one replaces it (a stamp against no stamp counts as greater).
        Within one page the same rule is applied here first, because
        PostgreSQL refuses to update one row twice in one statement.
        """
        if not rows:
            return
        names = (*self.natural_key, *self.columns)
        staged: dict[tuple[object, ...], dict[str, object]] = {}
        for row in rows:
            key = tuple(row[name] for name in self.natural_key)
            if key not in staged or self._is_newer(row, staged[key]):
                staged[key] = {"id": self._row_id(row), **{name: row[name] for name in names}}
        dialect_insert = (
            postgresql_insert if self.session.bind.dialect.name == "postgresql" else sqlite_insert
        )
        statement = dialect_insert(self.table)
        if self.newest is None:
            statement = statement.on_conflict_do_nothing()
        else:
            held, offered = self.table.c[self.newest], statement.excluded[self.newest]
            statement = statement.on_conflict_do_update(
                index_elements=self.natural_key,
                set_={name: statement.excluded[name] for name in self.columns},
                where=(held.is_(None) & offered.is_not(None)) | (offered > held),
            )
        await self.session.execute(statement, list(staged.values()))

    async def count(self) -> tuple[int, int]:
        """(staged rows, live rows) — what the pass would write over what."""
        staged = await self.session.scalar(select(func.count()).select_from(self.table))
        live = await self.session.scalar(select(func.count()).select_from(self.live))
        return int(staged or 0), int(live or 0)

    async def replace(self, actor: str, *, floor: float | None = DEFAULT_FLOOR) -> int:
        """Write the stage over the ledger; return how many rows it now holds.

        Two set statements inside the caller's transaction — delete every
        ledger row, insert every staged row — so a reader sees the old ledger
        or the new one and never a mix. `DELETE` rather than `TRUNCATE`
        because the latter takes an exclusive lock that would block every
        reader for the length of the insert, while a delete leaves them the
        old rows until the commit (and SQLite, where the tests run, has no
        truncate at all).

        Refused below the floor: a pass that came back with less than `floor`
        of the live rows leaves the ledger untouched and raises with both
        counts — the one guard between a provider's bad night and an empty
        table. An empty ledger has no floor, or the first load could never
        run; but an empty *pass* is refused whatever the ledger holds, because
        a feed that answered no rows at all is the shape of a window past the
        provider's ceiling (measured on data.go.kr, 2026-09-05: `num_of_rows`
        of 501 answers 200 with an empty list), and the first night is the
        one nothing else would catch.

        `floor=None` is no guard at all, empty pass included — for a derived
        table rebuilt off ledgers whose own floors already vouched for the
        rows: its size follows theirs, and a ledger whose records carry no
        list yields a legitimately empty derivation.
        """
        staged, live = await self.count()
        if floor is not None and staged < max(1, live * floor):
            raise LedgerFloorError(self.live.name, staged, live, floor)
        stage = self.table
        ledger = self.live

        await self.session.execute(delete(ledger))
        names = ("id", *self.natural_key, *self.columns)
        written = await self.session.execute(
            insert(ledger).from_select(
                [*names, "created_by", "updated_by"],
                select(*(stage.c[name] for name in names), literal(actor), literal(actor)),
            )
        )
        # A table just rewritten whole has statistics for the rows it no longer
        # holds, and autovacuum reaches ten million rows on its own schedule.
        # Measured 2026-09-09 on the ingredient table after a rebuild: the
        # planner expected 2,805 rows behind a material code and met 94,332,
        # chose a bitmap too small for them and spilled it lossy - 1.2s for a
        # page of products. ANALYZE runs inside the transaction on both
        # dialects and is the one statement that tells it what is there now.
        await self.session.execute(text(f"ANALYZE {ledger.name}"))
        return cast(CursorResult[Any], written).rowcount

    async def drop(self) -> None:
        await self.session.execute(DropTable(self.table, if_exists=True))

    def _row_id(self, row: Mapping[str, object]) -> UUID:
        """The id a row keeps across passes: a name-based uuid of its natural key.

        The ledger is rewritten every night, so a random id would change under
        every reference to a row. Minted from the table name and the key
        parts (`uuid5`, unit-separator joined so `("a", "bc")` and `("ab",
        "c")` differ), the same record gets the same id on every pass and on
        every host, and a bookmark taken from one night's ledger finds its row
        in the next.
        """
        parts = "\x1f".join(str(row[name]) for name in self.natural_key)
        return uuid5(NAMESPACE_URL, f"{self.live.name}\x1f{parts}")

    def _is_newer(self, offered: Mapping[str, object], held: Mapping[str, object]) -> bool:
        """The conflict clause read in Python: greater on `newest`, or a stamp against none."""
        if self.newest is None:
            return False
        after, before = offered[self.newest], held[self.newest]
        if after is None:
            return False
        return before is None or bool(after > before)  # type: ignore[operator]


# ============================================================
# Functions
# ============================================================


def synced_columns(model: type[Base], natural_key: Sequence[str]) -> tuple[str, ...]:
    """Every column a derived model declares beyond its key and the audit trail.

    A derived table that copies its ledger one for one names no column list
    of its own: the list is the model, so a column added to both is staged
    without a second statement, and one added to only one fails at the first
    rebuild instead of silently staying NULL.
    """
    table: Table = model.__table__  # type: ignore[assignment]
    skipped = {"id", *natural_key, *AUDIT_COLUMNS}
    return tuple(column.name for column in table.columns if column.name not in skipped)


async def scan_table(
    session: AsyncSession,
    model: type[Base],
    key: Sequence[str],
    columns: Sequence[str],
    size: int,
    where: ColumnElement[bool] | None = None,
) -> AsyncIterator[list[dict[str, Any]]]:
    """A table's rows, in pages of `size`, in `key` order - how a derivation reads a ledger.

    Keyed pagination (the page after the last key seen) rather than an offset,
    so a million-row table costs one index walk and not a longer one per page;
    `key` must be unique on the table for the walk to be complete, which a
    ledger's natural key is. Only `key` and `columns` are read, as dicts, so a
    derivation stages what it read without instantiating the ORM.

    `where` narrows the walk to the rows a derivation is about, when the ledger
    holds more than that: the 수입신고 ledger is every crossing and a product
    derivation reads the three 제품구분 that are products. The narrowing is
    the model's own constant, so four readers of one ledger agree on it.
    """
    table: Table = model.__table__  # type: ignore[assignment]
    keys = tuple(table.c[name] for name in key)
    names = (*key, *columns)
    query = select(*(table.c[name] for name in names)).order_by(*keys).limit(size)
    if where is not None:
        query = query.where(where)
    last: tuple[Any, ...] | None = None
    while True:
        page = query if last is None else query.where(tuple_(*keys) > tuple_(*last))
        rows = [dict(row) for row in (await session.execute(page)).mappings()]
        if not rows:
            return
        yield rows
        last = tuple(rows[-1][name] for name in key)
