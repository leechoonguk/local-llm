"""add food ledger qr storage table

Revision ID: 200
Revises: 199

푸드QR 보관·취급방법 원장 - our own copy of `getFoodQrSfkpTrmtInfo02`.

One row per printed 보관방법 문구: 2,868 rows over 2,155 라벨 (whole feed,
2026-09-13). `실온보관`, `냉장보관(0~10℃)`, `냉동보관(-18℃ 이하)` - a storage
band, which is not `food_item_report.shelf_life` (the 소비기한) and has no
column anywhere else in this database.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "200"
down_revision: str | Sequence[str] | None = "199"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_ledger_qr_storage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label_no", sa.String(length=32), nullable=False),
        sa.Column("detail_serial", sa.String(length=32), nullable=False),
        sa.Column("storage_text", sa.Text(), nullable=True),
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
            "label_no", "detail_serial", name="uq_food_ledger_qr_storage_natural_key"
        ),
    )
    op.create_index(
        op.f("ix_food_ledger_qr_storage_barcode_no"),
        "food_ledger_qr_storage",
        ["barcode_no"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_qr_storage_label_no"),
        "food_ledger_qr_storage",
        ["label_no"],
        unique=False,
    )
    op.create_index(
        "ix_food_ledger_qr_storage_source_updated_at",
        "food_ledger_qr_storage",
        ["source_updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_food_ledger_qr_storage_source_updated_at", table_name="food_ledger_qr_storage"
    )
    op.drop_index(op.f("ix_food_ledger_qr_storage_label_no"), table_name="food_ledger_qr_storage")
    op.drop_index(op.f("ix_food_ledger_qr_storage_barcode_no"), table_name="food_ledger_qr_storage")
    op.drop_table("food_ledger_qr_storage")
