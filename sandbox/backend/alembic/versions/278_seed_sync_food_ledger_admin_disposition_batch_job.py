"""seed sync food ledger admin disposition batch job

Revision ID: 278
Revises: 277

The schedule row for the 행정처분 feed. A job in no database runs in no
environment, so the code the scheduler registers gets its row in the same
change (`check-backend-batch`).

Friday 19:20 KST, in the small-feed slot behind 회수(19:00), 부적합(19:05),
시험항목(19:10) and 적용제외(19:15): the whole feed is 251 rows in one window
(2026-09-18), so the pass is two calls and costs the credential almost nothing.
Spaced from its siblings all the same - two jobs of one portal at one minute
would make one of them fail for a reason neither can report.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "278"
down_revision: str | Sequence[str] | None = "277"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-admin-disposition")


def _schedule_table():
    return table(
        "batch_schedule",
        column("id", sa.Uuid()),
        column("code", sa.String()),
        column("name", sa.String()),
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
                "code": "sync_food_ledger_admin_disposition",
                "name": "Sync food_ledger_admin_disposition",
                "cron": "20 19 * * 5",
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    schedule = _schedule_table()
    op.get_bind().execute(schedule.delete().where(schedule.c.id == JOB_ID))
