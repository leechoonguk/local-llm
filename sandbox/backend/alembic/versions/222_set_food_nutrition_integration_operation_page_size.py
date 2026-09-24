"""set food nutrition integration operation page size

Revision ID: 222
Revises: 221

500 is this service's measured ceiling (2026-09-05: 500 answers 500 rows, 501
and 1000 answer zero - the same shape as the end of the feed, which is why the
ceiling is bisected and not guessed). Walked at the job's old 100 the 319,060
records were 3,191 windows against 639, and this gateway's windows cost more the
deeper they are (363 ms at pages 1-200, 1,441 ms at page 1,400, measured
2026-09-14), so the narrow width was ~80 minutes for what 500 does in ~11.

The narrow feeds of this provider keep 100: B553748 (HACCP 표기정보) answers
`resultCode 13` at 101, and that is what made the width a job constant in the
first place - a constant one service's ceiling set for ten others.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "222"
down_revision: str | Sequence[str] | None = "221"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/operation:search-food-nutrition")
PAGE_SIZE = 500


def _operation_table() -> sa.TableClause:
    return table(
        "integration_operation",
        column("code", sa.String()),
        column("page_size", sa.Integer()),
    )


def upgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(
        operation.update()
        .where(operation.c.code == "search-food-nutrition")
        .values(page_size=PAGE_SIZE)
    )


def downgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(
        operation.update()
        .where(operation.c.code == "search-food-nutrition")
        .values(page_size=100)
    )
