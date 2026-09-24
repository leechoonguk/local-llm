"""the mfds job's schedule row names the ledger it swapped

Revisions 115-117 gave 축산물품목제조보고(원재료) (C006) an operation and a
ledger, and revisions 118-120 retired the barcode feed (I2570) and its ledger.
The job's `FEEDS` walks the newcomer where the old one stood (fourth, by
size: 569,588 rows by the portal's own `total_count`, 2026-09-07). The
schedule row's description lists the ledgers by name, so it is updated to
say so; the code, the cron and the id do not move.

Revision ID: 121
Revises: 120
Create Date: 2026-09-07 09:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "121"
down_revision: str | Sequence[str] | None = "120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_CODE = "sync_mfds_ledgers"

# As revision 114 wrote it.
WITH_BARCODE = (
    "Replaces the food_test_item, food_product_classification, food_raw_material, "
    "food_barcode, food_item_report and food_item_report_raw_material ledgers "
    "with a whole pass of their 식품안전나라 feeds (I2530, I2510, I2520, I2570, "
    "I1250, C002)."
)

WITH_LIVESTOCK = (
    "Replaces the food_test_item, food_product_classification, food_raw_material, "
    "food_livestock_item_report_raw_material, food_item_report and "
    "food_item_report_raw_material ledgers with a whole pass of their 식품안전나라 "
    "feeds (I2530, I2510, I2520, C006, I1250, C002)."
)


def _schedules() -> sa.TableClause:
    return table(
        "batch_schedule",
        column("code", sa.String()),
        column("description", sa.String()),
        column("updated_by", sa.String()),
    )


def _describe(description: str) -> None:
    schedules = _schedules()
    op.execute(
        schedules.update()
        .where(schedules.c.code == JOB_CODE)
        .values(description=description, updated_by="migration")
    )


def upgrade() -> None:
    """Upgrade schema."""
    _describe(WITH_LIVESTOCK)


def downgrade() -> None:
    """Downgrade schema."""
    _describe(WITH_BARCODE)
