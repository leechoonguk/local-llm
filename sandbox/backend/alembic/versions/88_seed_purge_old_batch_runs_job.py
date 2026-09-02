"""seed purge old batch runs job

Revision ID: 88
Revises: 87

실행·단위 로그는 밤마다 자란다(런 1행 + 창 ~54행). 90일 — 이번 달의 실패를 지난달과 비교할
수 있는 분기치 — 를 남기고 지운다. 04:00: 02:00의 동기화가 끝난 뒤, 아침 사용 전.


"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "88"
down_revision: str | Sequence[str] | None = "87"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/purge-old-batch-runs")
JOB_CODE = "purge_old_batch_runs"
# 04:00: after the 02:00 sync has finished, before anyone reads the log.
JOB_CRON = "0 4 * * *"


def upgrade() -> None:
    batch_schedule = table(
        "batch_schedule",
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
        batch_schedule,
        [
            {
                "id": JOB_ID,
                "code": JOB_CODE,
                "name": "Purge old batch runs",
                "description": (
                    "Deletes batch runs (and their steps, by cascade) that finished "
                    "more than 90 days ago."
                ),
                "cron": JOB_CRON,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    batch_schedule = table("batch_schedule", column("id", sa.Uuid()))
    op.get_bind().execute(batch_schedule.delete().where(batch_schedule.c.id == JOB_ID))
