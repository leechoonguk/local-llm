"""seed sync food ledger collection inspection batch job

Revision ID: 282
Revises: 281

The schedule row for the 수거검사 feed. A job in no database runs in no
environment, so the code the scheduler registers gets its row in the same
change (`check-backend-batch`).

**Thursday 19:00 KST, alone.** Seeded when this feed was a paged walk of 2,047
windows that needed a night to itself; revision 286 then replaced the walk with
the portal's file door (one request, about two minutes), which made the slot
generous rather than necessary. It stays: a slot nothing else uses costs
nothing, the file quota (ten a day a key) is untouched by the other jobs, and
the derive job that reads this ledger runs after every night's feeds anyway.

Thursday rather than Friday because Friday night already carries 회수(19:00),
부적합(19:05), 시험항목(19:10), 적용제외(19:15), 행정처분(19:20) and 바코드(22:00),
and Saturday carries the two million-row 품목보고 feeds.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "282"
down_revision: str | Sequence[str] | None = "281"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-collection-inspection")


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
                "code": "sync_food_ledger_collection_inspection",
                "name": "Sync food_ledger_collection_inspection",
                "cron": "0 19 * * 4",
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    schedule = _schedule_table()
    op.get_bind().execute(schedule.delete().where(schedule.c.id == JOB_ID))
