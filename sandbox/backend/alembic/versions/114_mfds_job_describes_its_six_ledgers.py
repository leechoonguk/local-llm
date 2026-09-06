"""the mfds job's schedule row names the two ledgers it gained

Revisions 112 and 113 gave `search-test-item` and `search-product-classification`
their ledgers - seeded at revision 64 and walked by nothing until then - and the
job's `FEEDS` walks them first, being the two smallest feeds of the portal
(3,393 and 9,633 rows, 2026-09-06). The schedule row's description lists the
ledgers by name, so it is updated to say six where it said four; the code, the
cron and the id do not move.

Revision ID: 114
Revises: 113
Create Date: 2026-09-06 22:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "114"
down_revision: str | Sequence[str] | None = "113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_CODE = "sync_mfds_ledgers"

# As revision 110 wrote it.
FOUR_LEDGERS = (
    "Replaces the food_barcode, food_raw_material, food_item_report and "
    "food_item_report_raw_material ledgers with a whole pass of their "
    "식품안전나라 feeds (I2570, I2520, I1250, C002)."
)

SIX_LEDGERS = (
    "Replaces the food_test_item, food_product_classification, food_raw_material, "
    "food_barcode, food_item_report and food_item_report_raw_material ledgers "
    "with a whole pass of their 식품안전나라 feeds (I2530, I2510, I2520, I2570, "
    "I1250, C002)."
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
    _describe(SIX_LEDGERS)


def downgrade() -> None:
    """Downgrade schema."""
    _describe(FOUR_LEDGERS)
