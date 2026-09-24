"""add food ledger qr label table

Revision ID: 181
Revises: 180

The 푸드QR 식품표시정보 ledger: one row per E라벨관리번호, 2,278 of them over the
whole feed (2026-09-12). `label_no` is unique on its own - every record's is
distinct - and the bounds are that walk's maxima: 관리번호 18, 바코드 14,
식품유형 54, 기능성정보 863 (`Text`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "181"
down_revision: str | Sequence[str] | None = "180"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_ledger_qr_label",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label_no", sa.String(length=32), nullable=False),
        sa.Column("food_label_serial", sa.String(length=32), nullable=True),
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
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        op.f("ix_food_ledger_qr_label_barcode_no"),
        "food_ledger_qr_label",
        ["barcode_no"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_qr_label_label_no"), "food_ledger_qr_label", ["label_no"], unique=True
    )
    op.create_index(
        "ix_food_ledger_qr_label_source_updated_at",
        "food_ledger_qr_label",
        ["source_updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_food_ledger_qr_label_source_updated_at", table_name="food_ledger_qr_label")
    op.drop_index(op.f("ix_food_ledger_qr_label_label_no"), table_name="food_ledger_qr_label")
    op.drop_index(op.f("ix_food_ledger_qr_label_barcode_no"), table_name="food_ledger_qr_label")
    op.drop_table("food_ledger_qr_label")
