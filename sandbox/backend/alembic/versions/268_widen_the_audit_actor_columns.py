"""widen the audit actor columns

Revision ID: 268
Revises: 267
Create Date: 2026-09-16

`AuditMixin.created_by`/`updated_by` were `String(50)`. A batch job signs its
rows `batch:<job code>`, and since the jobs were named after the ledgers they
fill (revision 259) three of those names are longer than that:
`batch:sync_food_ledger_livestock_item_report_raw_material` is 57 characters.
Measured 2026-09-15 19:04 KST: the job opened its run, wrote its first
integration call log, and the INSERT was refused - the portal was never called
and the run ended FAILED with no window walked.

**One revision for a mixin column.** The width is the mixin's, not a table's:
every table that carries the audit trail has the same two columns, and widening
them one table per revision would be 54 revisions of one decision, any subset of
which is a database where the same value fits in one table and not the next.
The unit of this migration is the mixin (rule://backend-migrations).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "268"
down_revision: str | Sequence[str] | None = "267"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PREVIOUS_LENGTH = 50

ACTOR_LENGTH = 80

COLUMNS = ("created_by", "updated_by")


def _tables(connection: sa.engine.Connection) -> list[str]:
    """Every table carrying the audit trail, read off the database itself."""
    rows = connection.execute(
        sa.text(
            "SELECT table_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name = 'created_by' "
            "ORDER BY table_name"
        )
    )
    return [name for (name,) in rows]


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    for table in _tables(connection):
        for column in COLUMNS:
            op.alter_column(table, column, type_=sa.String(length=ACTOR_LENGTH))


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()
    for table in _tables(connection):
        for column in COLUMNS:
            # Cut to what the narrower column can hold, through a bound table
            # rather than a SQL string: the same statement every reader can see
            # the scope of (rule://backend-migrations).
            bound = sa.table(table, sa.column(column, sa.String()))
            op.execute(bound.update().values({column: sa.func.left(bound.c[column], PREVIOUS_LENGTH)}))
            op.alter_column(table, column, type_=sa.String(length=PREVIOUS_LENGTH))
