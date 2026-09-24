"""add food ledger qr manufacture table

Revision ID: 203
Revises: 202

푸드QR 품목제조정보 원장 - our own copy of `getFoodQrProdMnfInfo02`.

One row per 품목제조보고 a label reports under: 2,976 rows over 2,162 라벨
(whole feed, 2026-09-13). It carries 소재지주소 (2,954) and 대표자 (2,972),
neither of which `food_item_report` holds, and `item_report_no` on every
row - the second feed (with 영양표시) that gives a label its 품목보고번호.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "203"
down_revision: str | Sequence[str] | None = "202"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_ledger_qr_manufacture",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label_no", sa.String(length=32), nullable=False),
        sa.Column("item_report_serial", sa.String(length=32), nullable=False),
        sa.Column("item_report_no", sa.String(length=32), nullable=True),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("representative_name", sa.String(length=120), nullable=True),
        sa.Column("site_address", sa.Text(), nullable=True),
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
            "label_no", "item_report_serial", name="uq_food_ledger_qr_manufacture_natural_key"
        ),
    )
    op.create_index(
        op.f("ix_food_ledger_qr_manufacture_barcode_no"),
        "food_ledger_qr_manufacture",
        ["barcode_no"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_qr_manufacture_item_report_no"),
        "food_ledger_qr_manufacture",
        ["item_report_no"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_qr_manufacture_label_no"),
        "food_ledger_qr_manufacture",
        ["label_no"],
        unique=False,
    )
    op.create_index(
        "ix_food_ledger_qr_manufacture_source_updated_at",
        "food_ledger_qr_manufacture",
        ["source_updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_food_ledger_qr_manufacture_source_updated_at", table_name="food_ledger_qr_manufacture"
    )
    op.drop_index(
        op.f("ix_food_ledger_qr_manufacture_label_no"), table_name="food_ledger_qr_manufacture"
    )
    op.drop_index(
        op.f("ix_food_ledger_qr_manufacture_item_report_no"), table_name="food_ledger_qr_manufacture"
    )
    op.drop_index(
        op.f("ix_food_ledger_qr_manufacture_barcode_no"), table_name="food_ledger_qr_manufacture"
    )
    op.drop_table("food_ledger_qr_manufacture")
