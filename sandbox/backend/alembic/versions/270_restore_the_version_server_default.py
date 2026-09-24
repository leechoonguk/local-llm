"""restore the version server default on the production ledgers

Revision ID: 270
Revises: 269
Create Date: 2026-09-16

`AuditMixin.version` carries `server_default="1"`, and every table but three has
it. Revisions 248, 249 and 250 - the three 생산실적 ledgers - wrote the column
`nullable=False` with no default, so the first INSERT that did not name the
column violated the constraint. Measured 2026-09-16 07:27 KST: 건기식 생산실적
walked its whole feed (321 windows, 316,747 records, no refusal) and then failed
replacing the ledger, with the night's work in a TEMP table nobody could write.

`alembic check` never saw it: autogenerate compares server defaults only when
`compare_server_default=True`, which `alembic/env.py` did not set. That is set in
the same change, so the next drift of this kind is a red gate and not a night.

The unit here is the mixin's column, as in revision 268: one decision, three
tables carrying the same copy of it (rule://backend-migrations).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "270"
down_revision: str | Sequence[str] | None = "269"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VERSION_DEFAULT = "1"


def _tables(connection: sa.engine.Connection) -> list[str]:
    """Every table whose AuditMixin `version` column carries no default."""
    rows = connection.execute(
        sa.text(
            "SELECT table_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name = 'version' "
            "AND column_default IS NULL ORDER BY table_name"
        )
    )
    return [name for (name,) in rows]


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    for table in _tables(connection):
        op.alter_column(table, "version", server_default=sa.text(VERSION_DEFAULT))


def downgrade() -> None:
    """Downgrade schema."""
    for table in ("food_ledger_production", "food_ledger_livestock_production",
                  "food_ledger_health_functional_production"):
        op.alter_column(table, "version", server_default=None)
