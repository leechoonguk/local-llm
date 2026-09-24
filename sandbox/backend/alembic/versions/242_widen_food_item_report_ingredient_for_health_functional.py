"""widen food item report ingredient for health functional

Revision ID: 242
Revises: 241
Create Date: 2026-09-15

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "242"
down_revision: str | Sequence[str] | None = "241"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "food_item_report_ingredient",
        sa.Column("ingredient_role", sa.String(length=16), nullable=True),
    )
    op.drop_constraint(
        "ck_food_item_report_ingredient_kind", "food_item_report_ingredient", type_="check"
    )
    op.create_check_constraint(
        "ck_food_item_report_ingredient_kind",
        "food_item_report_ingredient",
        "report_kind IN ('domestic', 'livestock', 'import', 'health_functional')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_food_item_report_ingredient_kind", "food_item_report_ingredient", type_="check"
    )
    op.create_check_constraint(
        "ck_food_item_report_ingredient_kind",
        "food_item_report_ingredient",
        "report_kind IN ('domestic', 'livestock', 'import')",
    )
    op.drop_column("food_item_report_ingredient", "ingredient_role")
