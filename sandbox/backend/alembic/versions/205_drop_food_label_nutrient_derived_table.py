"""drop food label nutrient derived table

Revision ID: 205
Revises: 204

The 푸드QR 영양표시 split is dropped from the label axis (2026-09-13). It worked -
25,663 lines landed, amounts and 1일 기준치 비율 in their own columns - but nothing
reads it: `food_nutrition` already answers what a product's nutrients are, per
100 g and over 319,060 products, where this covered 2,725 라벨. The ledger
(`food_ledger_qr_nutrition`) stays: it is the feed that carries a label's
품목보고번호 on every row, which is how `food_label` finds one.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "205"
down_revision: str | Sequence[str] | None = "204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_food_label_nutrient_item_report_no"), table_name="food_label_nutrient")
    op.drop_index(op.f("ix_food_label_nutrient_label_no"), table_name="food_label_nutrient")
    op.drop_index(op.f("ix_food_label_nutrient_name"), table_name="food_label_nutrient")
    op.drop_table("food_label_nutrient")


def downgrade() -> None:
    op.create_table(
        "food_label_nutrient",
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("label_no", sa.VARCHAR(length=32), autoincrement=False, nullable=False),
        sa.Column("position", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("item_report_no", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column("basis_name", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column(
            "basis_amount", sa.NUMERIC(precision=18, scale=6), autoincrement=False, nullable=True
        ),
        sa.Column("basis_unit", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column("name", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column("amount", sa.NUMERIC(precision=18, scale=6), autoincrement=False, nullable=True),
        sa.Column("unit", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column(
            "daily_value_pct", sa.NUMERIC(precision=18, scale=6), autoincrement=False, nullable=True
        ),
        sa.Column("kind_name", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column("format_name", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column("sequence_text", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("created_by", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column("updated_by", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.INTEGER(),
            server_default=sa.text("1"),
            autoincrement=False,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("food_label_nutrient_pkey")),
        sa.UniqueConstraint(
            "label_no",
            "position",
            name=op.f("uq_food_label_nutrient_natural_key"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(
        op.f("ix_food_label_nutrient_name"), "food_label_nutrient", ["name"], unique=False
    )
    op.create_index(
        op.f("ix_food_label_nutrient_label_no"), "food_label_nutrient", ["label_no"], unique=False
    )
    op.create_index(
        op.f("ix_food_label_nutrient_item_report_no"),
        "food_label_nutrient",
        ["item_report_no"],
        unique=False,
    )
