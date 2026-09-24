"""add food ledger qr nutrition table

Revision ID: 183
Revises: 182

The 푸드QR 영양표시정보 ledger: one row per printed panel entry, 25,663 of them
over 2,725 라벨 (whole feed, 2026-09-12). The pair (라벨관리번호,
영양표시상세일련번호) is the unique constraint - 25,663 distinct, where the detail
serial alone repeats (24,766). `item_report_no` is filled on every record and
indexed: it is what carries the label axis to `food_item_report`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "183"
down_revision: str | Sequence[str] | None = "182"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_ledger_qr_nutrition",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label_no", sa.String(length=32), nullable=False),
        sa.Column("item_report_serial", sa.String(length=32), nullable=True),
        sa.Column("item_report_no", sa.String(length=32), nullable=True),
        sa.Column("nutrition_label_serial", sa.String(length=32), nullable=True),
        sa.Column("nutrition_detail_serial", sa.String(length=32), nullable=False),
        sa.Column("barcode_no", sa.String(length=32), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("version_no", sa.String(length=32), nullable=True),
        sa.Column("valid_from", sa.String(length=20), nullable=True),
        sa.Column("valid_to", sa.String(length=20), nullable=True),
        sa.Column("basis_name", sa.String(length=120), nullable=True),
        sa.Column("total_content_amount", sa.String(length=32), nullable=True),
        sa.Column("total_content_unit", sa.String(length=32), nullable=True),
        sa.Column("unit_content_amount", sa.String(length=32), nullable=True),
        sa.Column("unit_content_unit", sa.String(length=32), nullable=True),
        sa.Column("remark_text", sa.Text(), nullable=True),
        sa.Column("format_name", sa.String(length=120), nullable=True),
        sa.Column("label_group_name", sa.Text(), nullable=True),
        sa.Column("unit_content_label_name", sa.String(length=120), nullable=True),
        sa.Column("unit_content_label_amount_name", sa.String(length=120), nullable=True),
        sa.Column("total_piece_label_name", sa.String(length=120), nullable=True),
        sa.Column("nutrient_kind_name", sa.String(length=120), nullable=True),
        sa.Column("nutrient_name", sa.String(length=120), nullable=True),
        sa.Column("nutrient_sequence", sa.String(length=32), nullable=True),
        sa.Column("amount", sa.String(length=32), nullable=True),
        sa.Column("amount_unit", sa.String(length=32), nullable=True),
        sa.Column("amount_unit_etc", sa.String(length=32), nullable=True),
        sa.Column("daily_value_pct", sa.String(length=32), nullable=True),
        sa.Column("additional_item_division_yn", sa.String(length=4), nullable=True),
        sa.Column("additional_item_division_name", sa.String(length=120), nullable=True),
        sa.Column("additional_item_1_name", sa.String(length=120), nullable=True),
        sa.Column("additional_item_2_name", sa.String(length=120), nullable=True),
        sa.Column("additional_item_3_name", sa.String(length=120), nullable=True),
        sa.Column("additional_item_4_name", sa.String(length=120), nullable=True),
        sa.Column("additional_item_5_name", sa.String(length=120), nullable=True),
        sa.Column("additional_item_1_amount", sa.String(length=32), nullable=True),
        sa.Column("additional_item_2_amount", sa.String(length=32), nullable=True),
        sa.Column("additional_item_3_amount", sa.String(length=32), nullable=True),
        sa.Column("additional_item_4_amount", sa.String(length=32), nullable=True),
        sa.Column("additional_item_5_amount", sa.String(length=32), nullable=True),
        sa.Column("additional_item_1_ratio", sa.String(length=32), nullable=True),
        sa.Column("additional_item_2_ratio", sa.String(length=32), nullable=True),
        sa.Column("additional_item_3_ratio", sa.String(length=32), nullable=True),
        sa.Column("additional_item_4_ratio", sa.String(length=32), nullable=True),
        sa.Column("additional_item_5_ratio", sa.String(length=32), nullable=True),
        sa.Column("additional_item_1_unit_etc", sa.String(length=32), nullable=True),
        sa.Column("additional_item_2_unit_etc", sa.String(length=32), nullable=True),
        sa.Column("additional_item_3_unit_etc", sa.String(length=32), nullable=True),
        sa.Column("additional_item_4_unit_etc", sa.String(length=32), nullable=True),
        sa.Column("additional_item_5_unit_etc", sa.String(length=32), nullable=True),
        sa.Column("intake_basis_name", sa.String(length=120), nullable=True),
        sa.Column("intake_amount", sa.String(length=32), nullable=True),
        sa.Column("intake_amount_unit", sa.String(length=32), nullable=True),
        sa.Column("intake_weight", sa.String(length=32), nullable=True),
        sa.Column("intake_weight_unit", sa.String(length=32), nullable=True),
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
        sa.UniqueConstraint(
            "label_no", "nutrition_detail_serial", name="uq_food_ledger_qr_nutrition_natural_key"
        ),
    )
    op.create_index(
        op.f("ix_food_ledger_qr_nutrition_barcode_no"),
        "food_ledger_qr_nutrition",
        ["barcode_no"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_qr_nutrition_item_report_no"),
        "food_ledger_qr_nutrition",
        ["item_report_no"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_qr_nutrition_label_no"),
        "food_ledger_qr_nutrition",
        ["label_no"],
        unique=False,
    )
    op.create_index(
        "ix_food_ledger_qr_nutrition_source_updated_at",
        "food_ledger_qr_nutrition",
        ["source_updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_food_ledger_qr_nutrition_source_updated_at", table_name="food_ledger_qr_nutrition"
    )
    op.drop_index(
        op.f("ix_food_ledger_qr_nutrition_label_no"), table_name="food_ledger_qr_nutrition"
    )
    op.drop_index(
        op.f("ix_food_ledger_qr_nutrition_item_report_no"), table_name="food_ledger_qr_nutrition"
    )
    op.drop_index(
        op.f("ix_food_ledger_qr_nutrition_barcode_no"), table_name="food_ledger_qr_nutrition"
    )
    op.drop_table("food_ledger_qr_nutrition")
