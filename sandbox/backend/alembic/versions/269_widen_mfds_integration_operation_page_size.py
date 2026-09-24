"""widen the mfds integration operation page size

Revision ID: 269
Revises: 268
Create Date: 2026-09-16

식품안전나라 answers up to 1,000 rows per window (measured: a wider start/end
returns `INFO-320`), and eleven of its seventeen OPERATIONS were left on the
column's `server_default` of 100 when the width moved from the job to the
operation. The jobs that used to walk those feeds in 1,000-row pages went on
walking them in 100-row ones, and nothing said so.

Measured 2026-09-15 on the barcode feed (259,680 records): 2,462 windows of 100
against 247 of 1,000, per-window latency rising 1.1 s → 12 s as the offset grew,
the whole walk 7.5 hours - and ten times the calls spent fifteen refusals and
locked all three keys for an hour. The six OPERATIONS already on 1,000
(recall, inspection failure, 건기식 품목·생산실적, 식품·축산 생산실적) were
seeded with an explicit width and never drifted.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision: str = "269"
down_revision: str | Sequence[str] | None = "268"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAGE_SIZE = 1000

PREVIOUS_PAGE_SIZE = 100

# The eleven 식품안전나라 OPERATIONS left on the column default.
OPERATION_CODES = (
    "search-barcode-product-info",
    "search-common-standard",
    "search-common-standard-exclusion",
    "search-common-standard-type",
    "search-food-item-report",
    "search-food-item-report-raw-material",
    "search-food-raw-material",
    "search-individual-standard",
    "search-livestock-item-report-raw-material",
    "search-product-classification",
    "search-test-item",
)

OPERATIONS = table(
    "integration_operation",
    column("code", sa.String()),
    column("page_size", sa.Integer()),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        OPERATIONS.update()
        .where(OPERATIONS.c.code.in_(OPERATION_CODES))
        .values(page_size=PAGE_SIZE)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        OPERATIONS.update()
        .where(OPERATIONS.c.code.in_(OPERATION_CODES))
        .values(page_size=PREVIOUS_PAGE_SIZE)
    )
