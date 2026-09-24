"""add skipped to batch run status

Revision ID: 261
Revises: 260
Create Date: 2026-09-15

`SKIPPED` is an ending the derive job needs: it fires every day and the ledgers
it reads are walked over three nights, so a fire that lands mid-walk has
nothing to rebuild against. Measured 2026-09-15 without this revision: the job
raised, the scheduler wrote the ending, the CHECK constraint refused it, and
the run stayed RUNNING for ever - the failure of a status vocabulary that lives
in three places and was changed in two.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision: str = "261"
down_revision: str | Sequence[str] | None = "260"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "ck_batch_run_status"

ENDINGS = "'RUNNING', 'SUCCEEDED', 'FAILED', 'STOPPED', 'INTERRUPTED', 'SKIPPED'"

PREVIOUS_ENDINGS = "'RUNNING', 'SUCCEEDED', 'FAILED', 'STOPPED', 'INTERRUPTED'"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(CONSTRAINT, "batch_run", type_="check")
    op.create_check_constraint(CONSTRAINT, "batch_run", f"status IN ({ENDINGS})")


def downgrade() -> None:
    """Downgrade schema."""
    runs = table("batch_run", column("status", sa.String()))
    op.execute(runs.update().where(runs.c.status == "SKIPPED").values(status="STOPPED"))
    op.drop_constraint(CONSTRAINT, "batch_run", type_="check")
    op.create_check_constraint(CONSTRAINT, "batch_run", f"status IN ({PREVIOUS_ENDINGS})")
