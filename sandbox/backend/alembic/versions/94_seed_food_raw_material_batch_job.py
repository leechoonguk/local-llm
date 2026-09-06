"""seed sync food raw material ledger batch job

스케줄은 데이터다: `sync_food_raw_material_ledger` 가 파이썬에만 있으면 어느
환경에서도 돌지 않는다 — 스케줄러는 `batch_schedule` 행을 읽어 트리거를 건다.

03:00, an hour after the barcode ledger's pass: the two jobs read the same portal
with the same credential, and a portal that refuses a second concurrent caller
would make one of them fail every night for a reason neither job could report.

Revision ID: 94
Revises: 93
Create Date: 2026-09-05 09:37:09.790683

"""

from collections.abc import Sequence

from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "94"
down_revision: str | Sequence[str] | None = "93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-raw-material-ledger")

JOB_CODE = "sync_food_raw_material_ledger"

JOB_CRON = "0 3 * * *"


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
                "name": "Sync food raw material ledger",
                "description": (
                    "Migrates 식품 원재료(I2520) records into the food_raw_material ledger, "
                    "resuming from the row cursor the previous run left."
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
