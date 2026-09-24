"""widen the item report read timeout to its siblings

`search-food-item-report` was the only 식품안전나라 paging operation left on a
15 s read timeout; every sibling that walks a million-row feed carries 30 s. The
gap is not cosmetic, because a walk is all-or-nothing: the pass stages every
window and replaces the ledger once at the end, so one window that never answers
throws away everything walked before it.

Measured on a QA pass of this feed: 967 windows walked over 2 h 45 m, response
times climbing with the offset (162 calls under 2 s near the start, 281 in the
6-8 s band, 21 past 14 s), and then window 968 timed out three times in a row -
45.9 s spent, `IntegrationTimeoutError`, the run FAILED and the ledger left at
the rows it had before. The same night, the two feeds on 30 s finished:
품목 원재료 and 바코드.

Revision ID: 283
Revises: 282
Create Date: 2026-09-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "283"
down_revision: str | Sequence[str] | None = "282"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# What every sibling walking this portal already allows one response.
READ_TIMEOUT_MS = 30000

PREVIOUS_READ_TIMEOUT_MS = 15000

OPERATION_CODE = "search-food-item-report"

OPERATIONS = table(
    "integration_operation",
    column("code", sa.String()),
    column("read_timeout_ms", sa.Integer()),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        OPERATIONS.update()
        .where(OPERATIONS.c.code == OPERATION_CODE)
        .values(read_timeout_ms=READ_TIMEOUT_MS)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        OPERATIONS.update()
        .where(OPERATIONS.c.code == OPERATION_CODE)
        .values(read_timeout_ms=PREVIOUS_READ_TIMEOUT_MS)
    )
