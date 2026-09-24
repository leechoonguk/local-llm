"""add food nutrition label derived table

Revision ID: 169
Revises: 168

The split of the HACCP label ledger's printed 영양표시: one row per entry,
keyed on (품목보고번호, 순번), each carrying the parsed amount and unit beside
the text it was parsed from. Measured on the first live rebuild (2026-09-12): of 14,666 labels, 8,948 read
as a panel and yield 83,951 entries (73,096 with a number); the rest is prose
the field was typed into and yields nothing.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "169"
down_revision: str | Sequence[str] | None = "168"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_nutrition_label",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_report_no", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
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
            "item_report_no", "position", name="uq_food_nutrition_label_natural_key"
        ),
    )
    op.create_index(
        op.f("ix_food_nutrition_label_item_report_no"),
        "food_nutrition_label",
        ["item_report_no"],
        unique=False,
    )
    op.create_index("ix_food_nutrition_label_name", "food_nutrition_label", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_food_nutrition_label_name", table_name="food_nutrition_label")
    op.drop_index(op.f("ix_food_nutrition_label_item_report_no"), table_name="food_nutrition_label")
    op.drop_table("food_nutrition_label")
