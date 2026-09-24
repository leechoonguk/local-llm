"""set import food label integration operation page size

Revision ID: 221
Revises: 220

500 is this service's measured ceiling (1000 and 5000 answer zero rows,
2026-09-13) and the width its whole feed was walked at: 2,176 windows, 66
minutes, 1,087,781 records.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "221"
down_revision: str | Sequence[str] | None = "220"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-import-food-label")
PAGE_SIZE = 500


def _operation_table() -> sa.TableClause:
    return table(
        "integration_operation",
        column("id", sa.Uuid()),
        column("page_size", sa.Integer()),
    )


def upgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(
        operation.update().where(operation.c.id == OPERATION_ID).values(page_size=PAGE_SIZE)
    )


def downgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(
        operation.update().where(operation.c.id == OPERATION_ID).values(page_size=100)
    )
