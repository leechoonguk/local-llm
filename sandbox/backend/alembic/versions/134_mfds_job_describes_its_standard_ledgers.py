"""the mfds job's schedule row names the four 기준규격 ledgers it walks

Revisions 122-133 gave the 기준규격 family of 식품안전나라 - 공통기준종류
(I2590), 공통기준제외 (I2610), 개별기준규격 (I2580), 공통기준규격 (I2600) -
an operation and a ledger each, and the job's `FEEDS` walks the four after
the product classification they hang off. The schedule row's description
lists the ledgers by name, so it is updated to say so; the code, the cron
and the id do not move.

The four are placed smallest first by their measured totals (2026-09-07,
after 19:00 KST - the services are closed 09:00-19:00, revision 122): I2610
21 → I2590 90 → I2580 16,401 → I2600 57,457, 77 windows of 1,000 in all,
walked within the first hour of a 00:00 start and so well clear of the
09:00 closure. The pass stays positional: the portal's `LAST_UPDT_DTM`
filter reaches back 7 days at most (ERROR-303 beyond), too short a leash
for an incremental read that may miss a night.

Revision ID: 134
Revises: 133
Create Date: 2026-09-07 10:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "134"
down_revision: str | Sequence[str] | None = "133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_CODE = "sync_mfds_ledgers"

# As revision 121 wrote it.
WITH_LIVESTOCK = (
    "Replaces the food_test_item, food_product_classification, food_raw_material, "
    "food_livestock_item_report_raw_material, food_item_report and "
    "food_item_report_raw_material ledgers with a whole pass of their 식품안전나라 "
    "feeds (I2530, I2510, I2520, C006, I1250, C002)."
)

WITH_STANDARDS = (
    "Replaces the food_test_item, food_product_classification, "
    "food_common_standard_exclusion, food_common_standard_type, "
    "food_individual_standard, food_common_standard, food_raw_material, "
    "food_livestock_item_report_raw_material, food_item_report and "
    "food_item_report_raw_material ledgers with a whole pass of their 식품안전나라 "
    "feeds (I2530, I2510, I2610, I2590, I2580, I2600, I2520, C006, I1250, C002)."
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
    _describe(WITH_STANDARDS)


def downgrade() -> None:
    """Downgrade schema."""
    _describe(WITH_LIVESTOCK)
