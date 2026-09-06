"""seed sync food nutrition ledger batch job

스케줄은 데이터다: `sync_food_nutrition_ledger` 가 파이썬에만 있으면 어느
환경에서도 돌지 않는다 — 스케줄러는 `batch_schedule` 행을 읽어 트리거를 건다.

05:00, clear of the two 식품안전나라 ledgers (02:00, 03:00) and of the purges
(03:00, 04:00). This feed is 639 calls at its widest window, the longest pass of
the four, so it runs where nothing else is holding a connection pool.

Revision ID: 97
Revises: 96
Create Date: 2026-09-05 11:01:05.490573

"""

from collections.abc import Sequence

from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "97"
down_revision: str | Sequence[str] | None = "96"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-nutrition-ledger")

JOB_CODE = "sync_food_nutrition_ledger"

JOB_CRON = "0 5 * * *"


def upgrade() -> None:
    """Upgrade schema."""
    schedules = table(
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
        schedules,
        [
            {
                "id": JOB_ID,
                "code": JOB_CODE,
                "name": "Sync food nutrition ledger",
                "description": (
                    "Migrates 식품 영양성분(I2790) records into the food_nutrition ledger, "
                    "resuming from the page cursor the previous run left."
                ),
                "cron": JOB_CRON,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    schedules = table("batch_schedule", column("id", sa.Uuid()))
    op.execute(schedules.delete().where(schedules.c.id == JOB_ID))
