"""carry the registry kind on food nutrition

Revision ID: 267
Revises: 266
Create Date: 2026-09-15

I2790 names a 품목제조보고번호 and not the registry that issued it, so the edge
to a product was the number alone - which belongs to whichever registry
numbered it. The derive job resolves the kind against the numbered report
ledgers; 172,476 of 319,060 records name a number (2026-09-09).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "267"
down_revision: str | Sequence[str] | None = "266"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("food_nutrition", sa.Column("report_kind", sa.String(length=32), nullable=True))
    op.create_index(
        op.f("ix_food_nutrition_report_kind"), "food_nutrition", ["report_kind"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_food_nutrition_report_kind"), table_name="food_nutrition")
    op.drop_column("food_nutrition", "report_kind")
