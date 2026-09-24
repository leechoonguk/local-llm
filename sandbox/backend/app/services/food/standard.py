# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import LedgerStage, scan_table, synced_columns
from app.models.food import standard as standard_model
from app.models.food.ledger_common_standard import FoodLedgerCommonStandard
from app.models.food.ledger_individual_standard import FoodLedgerIndividualStandard
from app.models.food.standard import FoodStandard


# ============================================================
# Constants
# ============================================================

# The ledgers are read in pages of this many rows: 57,457 + 16,408 rows, 75 pages.
PAGE_SIZE = 1000

# Every column the model declares beyond its key and the audit trail.
SYNCED_COLUMNS = synced_columns(FoodStandard, standard_model.NATURAL_KEY)

# Each chapter's ledger, the kind it is written under, the key its pages are
# walked in, and the column that numbers a clause there - I2600 calls it
# `common_standard_seq` and I2580 `individual_standard_seq`, and both mean
# "this registry's serial". The walk key is each ledger's own: I2600 is two
# columns and I2580 four, and a page is keyed by what its own table is keyed by.
LEDGERS = (
    (
        FoodLedgerCommonStandard,
        standard_model.COMMON_KIND,
        ("common_standard_seq", "test_item_code"),
        "common_standard_seq",
    ),
    (
        FoodLedgerIndividualStandard,
        standard_model.INDIVIDUAL_KIND,
        ("individual_standard_seq", "test_item_code", "detail_item_name", "clause_seq"),
        "individual_standard_seq",
    ),
)

# The two columns only I2600 publishes: 제5 hangs its clauses under no heading.
COMMON_ONLY_COLUMNS = ("common_standard_type_code", "common_standard_type_name")


# ============================================================
# Classes
# ============================================================


class FoodStandardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def rebuild_standard(self, synced_by: str) -> int:
        """Write `food_standard` as a function of the I2600 and I2580 ledgers; return its rows.

        Both ledgers whole - no filter: the derived table exists so that its
        edges can be declared on it and not on a ledger
        (rule://backend-relations). What this job decides is the kind each row
        is written under and the one name the two registries spell differently
        (`<chapter>_standard_seq` -> `standard_seq`); every other column is the
        ledger's own, one for one.

        Read off the live ledgers in keyed pages, staged, and written over in
        one short transaction (`LedgerStage.replace`, no floor: each ledger's
        own floor already vouched for the rows this reads).
        """
        stage = LedgerStage(self.session, FoodStandard, standard_model.NATURAL_KEY, SYNCED_COLUMNS)
        async with self.session.begin():
            await stage.create()
        try:
            async with self.session.begin():
                for model, kind, key, seq_column in LEDGERS:
                    columns = _ledger_columns(kind, seq_column)
                    async for page in scan_table(self.session, model, key, columns, PAGE_SIZE):
                        await stage.add([_clause(record, kind, seq_column) for record in page])
                return await stage.replace(synced_by, floor=None)
        finally:
            async with self.session.begin():
                await stage.drop()


# ============================================================
# Functions
# ============================================================


def _ledger_columns(kind: str, seq_column: str) -> tuple[str, ...]:
    """What to read off one chapter's ledger: its own serial, and the columns it answers."""
    names = [seq_column]
    for name in (*standard_model.NATURAL_KEY, *SYNCED_COLUMNS):
        if name in ("standard_kind", "standard_seq"):
            continue
        if kind == standard_model.INDIVIDUAL_KIND and name in COMMON_ONLY_COLUMNS:
            continue
        names.append(name)
    return tuple(names)


def _clause(row: Mapping[str, object], kind: str, seq_column: str) -> dict[str, object]:
    """One ledger row under this table's names.

    Every column the table declares is written, whether the ledger answers it or
    not: `common_standard_type_code`/`_name` are I2600's alone and land as NULL
    on a 제5 row, which is what "this registry does not publish it" looks like.

    `detail_item_name` and `clause_seq` are part of the key here, so they are
    written as the empty string rather than NULL: I2580 fills both on every row
    and I2600 leaves them empty, which is one row either way and not two.
    """
    values: dict[str, object] = {name: row.get(name) for name in SYNCED_COLUMNS}
    values["standard_kind"] = kind
    values["standard_seq"] = row.get(seq_column)
    values["test_item_code"] = row.get("test_item_code")
    values["detail_item_name"] = row.get("detail_item_name") or ""
    values["clause_seq"] = row.get("clause_seq") or ""
    return values
