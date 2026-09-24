"""add food label nutrient derived table

Revision ID: 185
Revises: 184

Table two: one row per printed panel line, 25,663 of them (2026-09-12). The
amounts are read as numbers here (25,585 printed, all of them readable) and the
1일 기준치 비율 is its own column (18,891 rows) - the split the retired HACCP
derivation had to guess at from one string, and got wrong (revision 170).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "185"
down_revision: str | Sequence[str] | None = "184"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_label_nutrient",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label_no", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("item_report_no", sa.String(length=32), nullable=True),
        sa.Column("basis_name", sa.String(length=120), nullable=True),
        sa.Column("basis_amount", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("basis_unit", sa.String(length=120), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("unit", sa.String(length=120), nullable=True),
        sa.Column("daily_value_pct", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("kind_name", sa.String(length=120), nullable=True),
        sa.Column("format_name", sa.String(length=120), nullable=True),
        sa.Column("sequence_text", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("label_no", "position", name="uq_food_label_nutrient_natural_key"),
    )
    op.create_index(
        "ix_food_label_nutrient_item_report_no",
        "food_label_nutrient",
        ["item_report_no"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_label_nutrient_label_no"), "food_label_nutrient", ["label_no"], unique=False
    )
    op.create_index("ix_food_label_nutrient_name", "food_label_nutrient", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_food_label_nutrient_name", table_name="food_label_nutrient")
    op.drop_index(op.f("ix_food_label_nutrient_label_no"), table_name="food_label_nutrient")
    op.drop_index("ix_food_label_nutrient_item_report_no", table_name="food_label_nutrient")
    op.drop_table("food_label_nutrient")
