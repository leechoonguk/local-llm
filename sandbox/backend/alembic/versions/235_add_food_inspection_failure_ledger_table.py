"""add food inspection failure ledger table

Revision ID: 235
Revises: 234
Create Date: 2026-09-14

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "235"
down_revision: str | Sequence[str] | None = "234"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "food_ledger_inspection_failure",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("disposal_seq", sa.String(length=32), nullable=False),
        sa.Column("test_item_name", sa.Text(), nullable=False),
        sa.Column("standard_text", sa.Text(), nullable=False),
        sa.Column("test_result_text", sa.Text(), nullable=True),
        sa.Column("institution_name", sa.Text(), nullable=True),
        sa.Column("item_report_no", sa.String(length=32), nullable=True),
        sa.Column("license_no", sa.String(length=32), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("barcode_no", sa.Text(), nullable=True),
        sa.Column("packaging_unit", sa.Text(), nullable=True),
        sa.Column("manufactured_text", sa.Text(), nullable=True),
        sa.Column("shelf_life_text", sa.Text(), nullable=True),
        sa.Column("product_type_name", sa.String(length=120), nullable=True),
        sa.Column("registered_on", sa.String(length=120), nullable=True),
        sa.Column("created_by", sa.String(length=50), nullable=True),
        sa.Column("updated_by", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "disposal_seq",
            "test_item_name",
            "standard_text",
            name="uq_food_ledger_inspection_failure_natural_key",
        ),
    )
    op.create_index(
        "ix_food_ledger_inspection_failure_item_report_no",
        "food_ledger_inspection_failure",
        ["item_report_no"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_inspection_failure_license_no"),
        "food_ledger_inspection_failure",
        ["license_no"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_food_ledger_inspection_failure_license_no"),
        table_name="food_ledger_inspection_failure",
    )
    op.drop_index(
        "ix_food_ledger_inspection_failure_item_report_no",
        table_name="food_ledger_inspection_failure",
    )
    op.drop_table("food_ledger_inspection_failure")
