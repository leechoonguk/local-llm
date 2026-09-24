"""add food label derived table

Revision ID: 184
Revises: 183

The 푸드QR label axis, table one of three: one row per E라벨관리번호, 2,278 of
them over the whole feed (2026-09-12). Its one column that is not the 표시사항
ledger's is `item_report_no`, read off the 영양표시 ledger - 2,068 labels have a
panel there and 1,911 of those resolve to a `food_item_report` row, which is
the edge this table exists to carry (the ledgers carry none,
rule://backend-relations).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "184"
down_revision: str | Sequence[str] | None = "183"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_label",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label_no", sa.String(length=32), nullable=False),
        sa.Column("item_report_no", sa.String(length=32), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("barcode_no", sa.String(length=32), nullable=True),
        sa.Column("version_no", sa.String(length=32), nullable=True),
        sa.Column("valid_from", sa.String(length=20), nullable=True),
        sa.Column("valid_to", sa.String(length=20), nullable=True),
        sa.Column("food_division_name", sa.String(length=120), nullable=True),
        sa.Column("food_type_name", sa.String(length=120), nullable=True),
        sa.Column("history_tracked_yn", sa.String(length=4), nullable=True),
        sa.Column("irradiated_yn", sa.String(length=4), nullable=True),
        sa.Column("gmo_yn", sa.String(length=4), nullable=True),
        sa.Column("infant_sale_marked_yn", sa.String(length=4), nullable=True),
        sa.Column("high_calorie_low_nutrition_yn", sa.String(length=4), nullable=True),
        sa.Column("pasteurized_yn", sa.String(length=4), nullable=True),
        sa.Column("sterilized_yn", sa.String(length=4), nullable=True),
        sa.Column("refrigerated_yn", sa.String(length=4), nullable=True),
        sa.Column("content_amount_text", sa.Text(), nullable=True),
        sa.Column("shelf_life_text", sa.Text(), nullable=True),
        sa.Column("intake_method_text", sa.Text(), nullable=True),
        sa.Column("functional_info_text", sa.Text(), nullable=True),
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
    op.create_index(op.f("ix_food_label_barcode_no"), "food_label", ["barcode_no"], unique=False)
    op.create_index("ix_food_label_item_report_no", "food_label", ["item_report_no"], unique=False)
    op.create_index(op.f("ix_food_label_label_no"), "food_label", ["label_no"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_food_label_label_no"), table_name="food_label")
    op.drop_index("ix_food_label_item_report_no", table_name="food_label")
    op.drop_index(op.f("ix_food_label_barcode_no"), table_name="food_label")
    op.drop_table("food_label")
