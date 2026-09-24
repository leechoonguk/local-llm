"""rename food item report kind

Revision ID: 223
Revises: 222

`food` became `domestic` and `import` joined it. The old value said which of two
registries answered, and with a third it says nothing: I1250 is 국내 제조 식품,
C006 is 축산물, and the 수입신고 feed (1,055,682 declarations over 292,867
products, 2026-09-14) is what crossed the border.

The rows are updated rather than left to the next rebuild, because the CHECK is
replaced in the same statement pair and a row reading `food` would fail it - and
because a derived table between two nightly runs is still what the screens read.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "223"
down_revision: str | Sequence[str] | None = "222"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "food_item_report"
CONSTRAINT = "ck_food_item_report_kind"


def _reports() -> sa.TableClause:
    return table("food_item_report", column("report_kind", sa.String()))


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
