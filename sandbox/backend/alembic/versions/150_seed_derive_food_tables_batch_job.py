"""seed derive food tables batch job

Revision ID: 150
Revises: 149

The four derived food tables (`food_product_classification`, `food_raw_material`,
`food_item_report`, `food_item_report_ingredient`) are functions of the ledgers,
rebuilt off them by one job once the ledger jobs' night is over - not written in
the ledgers' own passes as they were from revision 135 to here, where a rule that
changed cost a walk of the feed and four ledger services each knew a derived
table. The job skips while a provider job it depends on is still running.

The hour: the 식품안전나라 job starts at 00:00 and its pass was 6 h 05 m on
2026-09-07 for 2,258 windows, since grown to ~2,860 by C006 and the four 기준규격
feeds; 10:00 leaves it three hours past that measurement, and a night that ran
long is skipped and rebuilt the next day rather than rebuilt half-way.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "150"
down_revision: str | Sequence[str] | None = "149"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/derive-food-tables")
JOB_CODE = "derive_food_tables"

SCHEDULES = table(
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


def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(
        SCHEDULES,
        [
            {
                "id": JOB_ID,
                "code": JOB_CODE,
                "name": "Derive food tables",
                "description": (
                    "Rebuilds food_product_classification, food_raw_material, "
                    "food_item_report and food_item_report_ingredient off the "
                    "식품안전나라 ledgers once sync_mfds_ledgers is not running."
                ),
                "cron": "0 10 * * *",
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(SCHEDULES.delete().where(SCHEDULES.c.code == JOB_CODE))
