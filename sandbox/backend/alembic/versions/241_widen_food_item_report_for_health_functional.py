"""widen food item report for health functional

Revision ID: 241
Revises: 240
Create Date: 2026-09-15

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "241"
down_revision: str | Sequence[str] | None = "240"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("food_item_report", sa.Column("primary_functionality", sa.Text(), nullable=True))
    op.add_column("food_item_report", sa.Column("intake_caution", sa.Text(), nullable=True))
    op.add_column("food_item_report", sa.Column("storage_method", sa.Text(), nullable=True))
    op.add_column("food_item_report", sa.Column("standard_spec", sa.Text(), nullable=True))
    op.drop_constraint("ck_food_item_report_kind", "food_item_report", type_="check")
    op.create_check_constraint(
        "ck_food_item_report_kind",
        "food_item_report",
        "report_kind IN ('domestic', 'livestock', 'import', 'health_functional')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_food_item_report_kind", "food_item_report", type_="check")
    op.create_check_constraint(
        "ck_food_item_report_kind",
        "food_item_report",
        "report_kind IN ('domestic', 'livestock', 'import')",
    )
    op.drop_column("food_item_report", "standard_spec")
    op.drop_column("food_item_report", "storage_method")
    op.drop_column("food_item_report", "intake_caution")
    op.drop_column("food_item_report", "primary_functionality")
