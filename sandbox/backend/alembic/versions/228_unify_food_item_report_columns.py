"""unify food item report columns

Revision ID: 228
Revises: 227
Create Date: 2026-09-14

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "228"
down_revision: str | Sequence[str] | None = "227"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("food_item_report", "permit_date", new_column_name="report_date")
    op.add_column("food_item_report", sa.Column("maker_name", sa.Text(), nullable=True))
    op.add_column(
        "food_item_report", sa.Column("origin_country", sa.String(length=120), nullable=True)
    )
    op.add_column("food_item_report", sa.Column("product_name_en", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("food_item_report", "product_name_en")
    op.drop_column("food_item_report", "origin_country")
    op.drop_column("food_item_report", "maker_name")
    op.alter_column("food_item_report", "report_date", new_column_name="permit_date")
