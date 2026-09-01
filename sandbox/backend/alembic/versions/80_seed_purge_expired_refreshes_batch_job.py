"""seed purge expired refreshes batch job

Revision ID: 80
Revises: 79

The schedule is data, so the one job this build ships arrives the way every
other baseline row does: unconditionally, from the chain. Without the row the
refresh table grows by one row per login and nothing ever trims it — a job that
exists in Python but in no environment's database is a job that never runs.

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op


revision: str = "80"
down_revision: str | Sequence[str] | None = "79"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/purge-expired-refreshes")
JOB_CODE = "purge_expired_refreshes"
# 03:00 daily: after the nightly traffic trough starts and long before the
# morning login peak, so the deletes never compete with a rotation.
JOB_CRON = "0 3 * * *"


def upgrade() -> None:
    batch = table(
        "batch",
        column("id", sa.Uuid()),
        column("code", sa.String()),
        column("name", sa.String()),
        column("description", sa.String()),
        column("cron", sa.String()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )
    op.bulk_insert(
        batch,
        [
            {
                "id": JOB_ID,
                "code": JOB_CODE,
                "name": "Purge expired refresh tokens",
                "description": "Deletes refresh tokens that expired more than 30 days ago.",
                "cron": JOB_CRON,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    batch = table("batch", column("id", sa.Uuid()))
    op.get_bind().execute(batch.delete().where(batch.c.id == JOB_ID))
