"""address the production operations by year

생산실적 is published per 보고년도, and a walk that restarts its offset at every
year costs a fraction of one flat run: this gateway scans the OFFSET it is given,
so a window's cost grows with the rows already passed and a walk's cost with the
square of its windows. Measured inside one year of I0300 (1,034,296 rows):
0.92 s per window at offset 0, 6.36 s past 1,000,000 - a slope of 5.3 ms per
1,000 rows, which over the whole 7,927,213-row feed is ~48 h in one run against
~6 h year by year.

Which coordinate splits a feed, and the oldest value worth asking for, are facts
about the service - the same kind as its window width (revision 269) and its
quota codes - so they are stated here rather than in the job that walks it. 2015
and earlier answer nothing on any 생산실적 service.

Revision ID: 272
Revises: 271
Create Date: 2026-09-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "272"
down_revision: str | Sequence[str] | None = "271"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The caller input each 생산실적 service is addressed by.
SEGMENT_KEY = "report_year"

# The 보고년도 values these services publish, plus the five the portal has not
# opened yet: a value nothing answers for costs one window of one row and is
# skipped, so listing ahead is how January arrives without a migration.
SEGMENT_VALUES = [str(year) for year in range(2016, 2031)]

# The three 식품안전나라 services published per 보고년도.
OPERATION_CODES = (
    "search-food-production",
    "search-livestock-production",
    "search-health-functional-production",
)

OPERATIONS = table(
    "integration_operation",
    column("code", sa.String()),
    column("segment_key", sa.String()),
    column("segment_values", sa.JSON()),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        OPERATIONS.update()
        .where(OPERATIONS.c.code.in_(OPERATION_CODES))
        .values(segment_key=SEGMENT_KEY, segment_values=SEGMENT_VALUES)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        OPERATIONS.update()
        .where(OPERATIONS.c.code.in_(OPERATION_CODES))
        .values(segment_key=None, segment_values=None)
    )
