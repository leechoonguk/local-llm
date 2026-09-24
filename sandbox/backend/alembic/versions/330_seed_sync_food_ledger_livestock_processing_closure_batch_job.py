"""seed sync food ledger livestock processing closure batch job

Revision ID: 330
Revises: 329
Create Date: 2026-09-22 22:18:54.116000

The schedule row for the 축산물 가공업 폐업정보 feed (I2824). A job in no database runs in
no environment, so the code the scheduler registers gets its row in the same
change (`check-backend-batch`).

Saturday 4:44 KST, ahead of the Saturday mfds group (05:00): the feed is one
file (0.2MB, 8,071 rows, 2026-09-23), so the pass is a download and a stage,
minutes rather than hours, and the lane's rule is smallest first. The file
door's quota is its own - ten a day per key and service - and a weekly pass
spends one.

Switched off, as every schedule row is since revision 298: activation is the
operator's act in the environment that wants it (`PATCH /batch/{id}`).
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "330"
down_revision: str | Sequence[str] | None = "329"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-livestock-processing-closure")


def _schedule_table():
    return table(
        "batch_schedule",
        column("id", sa.Uuid()),
        column("code", sa.String()),
        column("cron", sa.String()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def upgrade() -> None:
    op.bulk_insert(
        _schedule_table(),
        [
            {
                "id": JOB_ID,
                "code": "sync_food_ledger_livestock_processing_closure",
                "cron": "44 4 * * sat",
                "enabled": False,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    schedule = _schedule_table()
    op.get_bind().execute(schedule.delete().where(schedule.c.id == JOB_ID))
