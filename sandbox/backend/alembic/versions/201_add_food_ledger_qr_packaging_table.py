"""add food ledger qr packaging table

Revision ID: 201
Revises: 200

푸드QR 용기·포장재질 원장 - our own copy of `getFoodQrIndctPackInfo02`.

One row per packaging part: 6,914 rows over 3,809 라벨 (whole feed,
2026-09-13) - the widest label set of the 푸드QR family.

The key needs three parts: (라벨관리번호, 상세일련번호) collapses to 4,715
because the same part is reported under two 품목제조보고 serials, so the
serial completes it.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "201"
down_revision: str | Sequence[str] | None = "200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_ledger_qr_packaging",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label_no", sa.String(length=32), nullable=False),
        sa.Column("detail_serial", sa.String(length=32), nullable=False),
        sa.Column("item_report_serial", sa.String(length=32), nullable=False),
        sa.Column("packaging_text", sa.Text(), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("barcode_no", sa.String(length=32), nullable=True),
        sa.Column("version_no", sa.String(length=32), nullable=True),
        sa.Column("valid_from", sa.String(length=20), nullable=True),
        sa.Column("valid_to", sa.String(length=20), nullable=True),
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
            "label_no",
            "detail_serial",
            "item_report_serial",
            name="uq_food_ledger_qr_packaging_natural_key",
        ),
    )
    op.create_index(
        op.f("ix_food_ledger_qr_packaging_barcode_no"),
        "food_ledger_qr_packaging",
        ["barcode_no"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_qr_packaging_label_no"),
        "food_ledger_qr_packaging",
        ["label_no"],
        unique=False,
    )
    op.create_index(
        "ix_food_ledger_qr_packaging_source_updated_at",
        "food_ledger_qr_packaging",
        ["source_updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_food_ledger_qr_packaging_source_updated_at", table_name="food_ledger_qr_packaging"
    )
    op.drop_index(
        op.f("ix_food_ledger_qr_packaging_label_no"), table_name="food_ledger_qr_packaging"
    )
    op.drop_index(
        op.f("ix_food_ledger_qr_packaging_barcode_no"), table_name="food_ledger_qr_packaging"
    )
    op.drop_table("food_ledger_qr_packaging")
