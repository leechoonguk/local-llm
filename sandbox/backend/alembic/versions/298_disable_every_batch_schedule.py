"""disable every batch schedule

Activation is a QA decision, not a deployment's. A schedule arrives with
`enabled` true because that is the column's default, so a seeded job starts
running on the clock of whatever database the revision is applied to - and four
of the 33 rows were doing exactly that (sync_food_ledger_recall,
_admin_disposition, _inspection_failure, _collection_inspection). Every row is
switched off here, and QA switches on the ones it wants.

The cron stays: `enabled` is activation, never the schedule itself, so
switching a job back on is one flag and not a cron retyped from memory.

The downgrade refuses. Which rows were on is not derivable from the rows
themselves, and a downgrade that guessed a set of jobs to start on the clock
would be worse than one that fails: the way back is to switch on the schedules
QA wants, which is the same act as switching them on in the first place.

Revision ID: 298
Revises: 297
Create Date: 2026-09-22 19:01:50.949787

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "298"
down_revision: str | Sequence[str] | None = "297"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    schedules = sa.table(
        "batch_schedule",
        sa.column("enabled", sa.Boolean),
    )
    op.execute(schedules.update().values(enabled=False))


def downgrade() -> None:
    """Downgrade schema."""
    raise NotImplementedError(
        "Which schedules were enabled is not recorded anywhere this revision can read; "
        "re-enable the jobs QA wants instead of restoring a guess"
    )
