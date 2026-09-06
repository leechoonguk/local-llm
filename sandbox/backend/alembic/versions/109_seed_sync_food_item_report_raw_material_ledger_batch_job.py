"""seed sync food item report raw material ledger batch job

스케줄은 데이터다: `sync_food_item_report_raw_material_ledger` 가 파이썬에만
있으면 어느 환경에서도 돌지 않는다 — 스케줄러는 `batch_schedule` 행을 읽어
트리거를 건다.

00:00, the hour before the item report ledger (01:00) and clear of the other
식품안전나라 ledgers (02:00, 03:00): this portal allows 100 unfiltered calls per
hour per key, and a full pass of this feed is ~1,072 windows (1,071,963 records,
2026-09-06) - so the initial load takes eleven nights by construction, and the
hour it runs in must not be shared with a sibling spending the same quota.

Revision ID: 109
Revises: 108
Create Date: 2026-09-05 13:35:16.418076

"""

from collections.abc import Sequence

from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "109"
down_revision: str | Sequence[str] | None = "108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-item-report-raw-material-ledger")

JOB_CODE = "sync_food_item_report_raw_material_ledger"

JOB_CRON = "0 0 * * *"


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
                "name": "Sync food item report raw material ledger",
                "description": (
                    "Migrates 식품(첨가물) 품목제조보고(원재료)(C002) records into the "
                    "food_item_report_raw_material ledger, resuming from the row cursor "
                    "the previous run left."
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
