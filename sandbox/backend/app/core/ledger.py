# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, NamedTuple, cast
from uuid import uuid4

from sqlalchemy import (
    Column,
    CursorResult,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    and_,
    delete,
    func,
    insert,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateTable, DropTable

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


# ============================================================
# Classes
# ============================================================


class Feed(NamedTuple):
    """One operation of a provider and the ledger method that replaces it.

    A provider job is a tuple of these: the walk reads `operation_code`, the
    job builds `service` on the pinned ledger session and hands the pages to
    `replace` (`replace_<table>_ledger`), which answers (received, changed).
    """

    operation_code: str
    service: Callable[[AsyncSession], Any]
    replace: Callable[..., Awaitable[tuple[int, int]]]


class LedgerStage:
    """A whole feed pass in a TEMP table, merged into its ledger in one statement each.

    A ledger is our copy of a provider's feed, and a pass reads the whole feed
    — so the ledger after a pass *is* the pass. Merging through a stage rather
    than writing the ledger as pages arrive keeps that true without a
    transaction that spans the walk: pages commit into the stage one by one
    (a pass over a million rows spans hours and quota waits), and the ledger
    changes in one short transaction at the end. Rows the feed dropped are
    deleted, rows it changed are updated, rows it added are inserted, and a
    row it re-sent unchanged is left alone — `updated_at` and `version` keep
    meaning "this record changed", and `id`/`created_at` survive a pass, so a
    reference to a ledger row from elsewhere stays valid.

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
    ) -> None:
        self.session = session
        self.live: Table = model.__table__  # type: ignore[assignment]
        self.natural_key = tuple(natural_key)
        self.columns = tuple(columns)
        # The staged shape: an id minted here so the insert can copy it, the
        # natural key as primary key (what the dedupe and the merge join on),
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
        """Stage one page; a natural key the pass already staged is skipped.

        Skipped rather than refused because the provider re-sends: a window
        overlapping a row the feed shifted under the walk hands the same
        record twice, and the first reading is as good as the second. The
        dedupe is the database's own conflict clause, so it holds within a
        page as well as across pages.
        """
        if not rows:
            return
        names = (*self.natural_key, *self.columns)
        staged = [{"id": uuid4(), **{name: row[name] for name in names}} for row in rows]
        dialect_insert = (
            postgresql_insert if self.session.bind.dialect.name == "postgresql" else sqlite_insert
        )
        await self.session.execute(dialect_insert(self.table).on_conflict_do_nothing(), staged)

    async def count(self) -> tuple[int, int]:
        """(staged rows, live rows) — what the merge would replace with what."""
        staged = await self.session.scalar(select(func.count()).select_from(self.table))
        live = await self.session.scalar(select(func.count()).select_from(self.live))
        return int(staged or 0), int(live or 0)

    async def merge(self, actor: str, *, floor: float = DEFAULT_FLOOR) -> int:
        """Make the ledger equal the stage; return how many rows that changed.

        Three set statements — delete what the feed no longer has, update what
        it changed, insert what it added — inside the caller's transaction, so
        a reader sees the old ledger or the new one and never a mix. The
        update touches only rows where a synced column differs
        (`IS DISTINCT FROM`, so a NULL on either side counts as a difference
        and NULL against NULL does not), which is what keeps `updated_at`
        honest.

        Refused below the floor: a pass that came back with less than `floor`
        of the live rows leaves the ledger untouched and raises with both
        counts — the one guard between a provider's bad night and an empty
        table. An empty ledger has no floor, or the first load could never
        run; but an empty *pass* is refused whatever the ledger holds, because
        a feed that answered no rows at all is the shape of a window past the
        provider's ceiling (measured on data.go.kr, 2026-09-05: `num_of_rows`
        of 501 answers 200 with an empty list), and the first night is the
        one nothing else would catch.
        """
        staged, live = await self.count()
        if staged < max(1, live * floor):
            raise LedgerFloorError(self.live.name, staged, live, floor)
        stage = self.table
        ledger = self.live
        key_match = and_(*(ledger.c[name] == stage.c[name] for name in self.natural_key))
        key_column = self.natural_key[0]

        gone = await self.session.execute(
            delete(ledger).where(~select(stage.c[key_column]).where(key_match).exists())
        )
        changed = await self.session.execute(
            update(ledger)
            .where(
                key_match,
                or_(*(ledger.c[name].is_distinct_from(stage.c[name]) for name in self.columns)),
            )
            .values(
                {
                    **{name: stage.c[name] for name in self.columns},
                    "updated_by": actor,
                    "updated_at": func.now(),
                    "version": ledger.c.version + 1,
                }
            )
        )
        names = ("id", *self.natural_key, *self.columns)
        added = await self.session.execute(
            insert(ledger).from_select(
                [*names, "created_by", "updated_by"],
                select(*(stage.c[name] for name in names), literal(actor), literal(actor)).where(
                    ~select(ledger.c[key_column]).where(key_match).exists()
                ),
            )
        )
        return sum(cast(CursorResult[Any], result).rowcount for result in (gone, changed, added))

    async def drop(self) -> None:
        await self.session.execute(DropTable(self.table, if_exists=True))
