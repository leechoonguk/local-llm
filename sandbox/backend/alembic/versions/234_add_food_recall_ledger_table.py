"""add food recall ledger table

Revision ID: 234
Revises: 233
Create Date: 2026-09-14

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "234"
down_revision: str | Sequence[str] | None = "233"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "food_ledger_recall",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recall_disuse_seq", sa.String(length=32), nullable=False),
        sa.Column("item_report_no", sa.String(length=32), nullable=True),
        sa.Column("license_no", sa.String(length=32), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("telephone", sa.Text(), nullable=True),
        sa.Column("barcode_no", sa.Text(), nullable=True),
        sa.Column("packaging_unit", sa.Text(), nullable=True),
        sa.Column("manufactured_text", sa.Text(), nullable=True),
        sa.Column("recall_reason", sa.Text(), nullable=True),
        sa.Column("recall_method", sa.Text(), nullable=True),
        sa.Column("recall_grade", sa.String(length=120), nullable=True),
        sa.Column("shelf_life_text", sa.Text(), nullable=True),
        sa.Column("product_type_group", sa.String(length=120), nullable=True),
        sa.Column("product_code", sa.String(length=32), nullable=True),
        sa.Column("product_type_name", sa.String(length=120), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("recall_disuse_seq", name="uq_food_ledger_recall_natural_key"),
    )
    op.create_index(
        "ix_food_ledger_recall_item_report_no",
        "food_ledger_recall",
        ["item_report_no"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_recall_license_no"), "food_ledger_recall", ["license_no"], unique=False
    )
    op.create_index(
        op.f("ix_food_ledger_recall_registered_at"),
        "food_ledger_recall",
        ["registered_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_food_ledger_recall_registered_at"), table_name="food_ledger_recall")
    op.drop_index(op.f("ix_food_ledger_recall_license_no"), table_name="food_ledger_recall")
    op.drop_index("ix_food_ledger_recall_item_report_no", table_name="food_ledger_recall")
    op.drop_table("food_ledger_recall")
