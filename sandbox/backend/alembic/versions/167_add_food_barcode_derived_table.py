"""add food barcode derived table

Revision ID: 167
Revises: 166

The derivation of the C005 ledger: one row per (유통바코드, 품목보고번호)
pair, 246,195 of them over the feed's 259,669 records (2026-09-12). The table
exists so that the edge to `food_item_report` lives on a derived table and
not on the ledger (rule://backend-relations).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "167"
down_revision: str | Sequence[str] | None = "166"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_barcode",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("barcode_no", sa.String(length=32), nullable=False),
        sa.Column("item_report_no", sa.String(length=32), nullable=False),
        sa.Column("permit_date", sa.String(length=20), nullable=True),
        sa.Column("production_end_date", sa.String(length=20), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("shelf_life", sa.Text(), nullable=True),
        sa.Column("product_type_name", sa.String(length=120), nullable=True),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("industry_name", sa.String(length=120), nullable=True),
        sa.Column("site_address", sa.String(length=120), nullable=True),
        sa.Column("closed_business_date", sa.String(length=20), nullable=True),
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
        sa.UniqueConstraint("barcode_no", "item_report_no", name="uq_food_barcode_natural_key"),
    )
    op.create_index(
        op.f("ix_food_barcode_barcode_no"), "food_barcode", ["barcode_no"], unique=False
    )
    op.create_index(
        "ix_food_barcode_item_report_no", "food_barcode", ["item_report_no"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_food_barcode_item_report_no", table_name="food_barcode")
    op.drop_index(op.f("ix_food_barcode_barcode_no"), table_name="food_barcode")
    op.drop_table("food_barcode")
