"""add food ledger haccp label table

Revision ID: 165
Revises: 164

The ledger `search-haccp-label` (revision 160) fills: one row per
품목보고번호, 14,666 of them over the whole feed (2026-09-12). The column
bounds are that walk's maxima - 유형명 67, 유형의상태 89, 축산/식품구분 4 -
and everything the certifying body typed is `Text`, so a label longer than
any measured one cannot fail a night's page (`rule://backend-ledger`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "165"
down_revision: str | Sequence[str] | None = "164"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_ledger_haccp_label",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_report_no", sa.String(length=32), nullable=False),
        sa.Column("product_kind_division", sa.String(length=120), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("raw_material_names", sa.Text(), nullable=True),
        sa.Column("allergy_names", sa.Text(), nullable=True),
        sa.Column("nutrient_text", sa.Text(), nullable=True),
        sa.Column("barcode_numbers", sa.Text(), nullable=True),
        sa.Column("product_type_name", sa.String(length=120), nullable=True),
        sa.Column("product_type_state", sa.String(length=120), nullable=True),
        sa.Column("maker_name", sa.Text(), nullable=True),
        sa.Column("seller_name", sa.Text(), nullable=True),
        sa.Column("capacity_text", sa.Text(), nullable=True),
        sa.Column("product_image_url", sa.Text(), nullable=True),
        sa.Column("label_image_url", sa.Text(), nullable=True),
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
    )
    op.create_index(
        op.f("ix_food_ledger_haccp_label_item_report_no"),
        "food_ledger_haccp_label",
        ["item_report_no"],
        unique=True,
    )
    op.create_index(
        "ix_food_ledger_haccp_label_product_type_name",
        "food_ledger_haccp_label",
        ["product_type_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_food_ledger_haccp_label_product_type_name", table_name="food_ledger_haccp_label"
    )
    op.drop_index(
        op.f("ix_food_ledger_haccp_label_item_report_no"), table_name="food_ledger_haccp_label"
    )
    op.drop_table("food_ledger_haccp_label")
