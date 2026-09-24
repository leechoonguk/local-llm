"""add food livestock production ledger table

Revision ID: 249
Revises: 248
Create Date: 2026-09-15

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "249"
down_revision: str | Sequence[str] | None = "248"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "food_ledger_livestock_production",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_report_no", sa.String(length=32), nullable=False),
        sa.Column("report_year", sa.String(length=8), nullable=False),
        sa.Column("product_name", sa.Text(), nullable=False),
        sa.Column("license_no", sa.String(length=32), nullable=False),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("product_type_name", sa.String(length=200), nullable=True),
        sa.Column("production_qty", sa.String(length=32), nullable=True),
        sa.Column("annual_capacity_qty", sa.String(length=32), nullable=True),
        sa.Column("product_kind_name", sa.String(length=200), nullable=True),
        sa.Column("created_by", sa.String(length=50), nullable=True),
        sa.Column("updated_by", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_food_ledger_livestock_production_item_report_no"), "food_ledger_livestock_production", ["item_report_no"], unique=False
    )
    op.create_index(
        op.f("ix_food_ledger_livestock_production_report_year"), "food_ledger_livestock_production", ["report_year"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_food_ledger_livestock_production_report_year"), table_name="food_ledger_livestock_production")
    op.drop_index(op.f("ix_food_ledger_livestock_production_item_report_no"), table_name="food_ledger_livestock_production")
    op.drop_table("food_ledger_livestock_production")
