"""drop food nutrition label derived table

Revision ID: 170
Revises: 169

The HACCP 표기정보 feed is retired (revisions 170-174) and this table was its
split. Measured before dropping it (2026-09-12, first live rebuild): 83,951
rows over 8,948 products, and the split was wrong - a panel's 실제 함량 and
its 1일 기준치 비율 both read as numbers, so `탄수화물4g 1%` stored the name
as `탄수화물4g` with amount 1 and unit `%`, and 21,327 distinct names came
out of what should be a few dozen. 푸드QR answers the same panel with the
value, the unit, the basis and the ratio in their own columns, so the label
axis is rebuilt on that instead.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "170"
down_revision: str | Sequence[str] | None = "169"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_food_nutrition_label_item_report_no"), table_name="food_nutrition_label")
    op.drop_index(op.f("ix_food_nutrition_label_name"), table_name="food_nutrition_label")
    op.drop_table("food_nutrition_label")


def downgrade() -> None:
    op.create_table(
        "food_nutrition_label",
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("item_report_no", sa.VARCHAR(length=32), autoincrement=False, nullable=False),
        sa.Column("position", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=120), autoincrement=False, nullable=False),
        sa.Column("amount", sa.NUMERIC(precision=18, scale=6), autoincrement=False, nullable=True),
        sa.Column("unit", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.Column("text", sa.TEXT(), autoincrement=False, nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("food_nutrition_label_pkey")),
        sa.UniqueConstraint(
            "item_report_no",
            "position",
            name=op.f("uq_food_nutrition_label_natural_key"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(
        op.f("ix_food_nutrition_label_name"), "food_nutrition_label", ["name"], unique=False
    )
    op.create_index(
        op.f("ix_food_nutrition_label_item_report_no"),
        "food_nutrition_label",
        ["item_report_no"],
        unique=False,
    )
