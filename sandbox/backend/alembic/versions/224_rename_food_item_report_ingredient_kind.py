"""rename food item report ingredient kind

Revision ID: 224
Revises: 223

The same three-value vocabulary on the ingredient table, whose rows hang off
`(report_kind, item_report_no)` of `food_item_report` (revision 223).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "224"
down_revision: str | Sequence[str] | None = "223"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "food_item_report_ingredient"
CONSTRAINT = "ck_food_item_report_ingredient_kind"


def _reports() -> sa.TableClause:
    return table("food_item_report_ingredient", column("report_kind", sa.String()))


def upgrade() -> None:
    reports = _reports()
    op.drop_constraint(CONSTRAINT, TABLE, type_="check")
    op.get_bind().execute(
        reports.update().where(reports.c.report_kind == "food").values(report_kind="domestic")
    )
    op.create_check_constraint(
        CONSTRAINT, TABLE, "report_kind IN ('domestic', 'livestock', 'import')"
    )


def downgrade() -> None:
    reports = _reports()
    op.drop_constraint(CONSTRAINT, TABLE, type_="check")
    op.get_bind().execute(reports.delete().where(reports.c.report_kind == "import"))
    op.get_bind().execute(
        reports.update().where(reports.c.report_kind == "domestic").values(report_kind="food")
    )
    op.create_check_constraint(CONSTRAINT, TABLE, "report_kind IN ('food', 'livestock')")
