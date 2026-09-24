"""add food ledger qr raw material table

Revision ID: 202
Revises: 201

푸드QR 원재료정보 원장 - our own copy of `getFoodQrProdRawmtrl02`.

One row per 원재료표시 그룹: 2,301 rows over 2,156 라벨 (whole feed,
2026-09-13). The text arrives as HTML on every row - each name wrapped in a
네이버 사전 link, each origin in `<p class="bold">` - and is stored as sent,
because a ledger is the feed. The derivation strips the tags.

It is not a copy of `food_item_report_ingredient`: measured on the 2,012
products both cover, this text carries a 함량 on 913 and an 원산지 on 1,594,
where the registry split carries neither.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202"
down_revision: str | Sequence[str] | None = "201"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_ledger_qr_raw_material",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label_no", sa.String(length=32), nullable=False),
        sa.Column("raw_material_serial", sa.String(length=32), nullable=False),
        sa.Column("raw_material_group_name", sa.String(length=120), nullable=True),
        sa.Column("raw_material_html", sa.Text(), nullable=True),
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
            "label_no", "raw_material_serial", name="uq_food_ledger_qr_raw_material_natural_key"
        ),
    )
    op.create_index(
        op.f("ix_food_ledger_qr_raw_material_barcode_no"),
        "food_ledger_qr_raw_material",
        ["barcode_no"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_qr_raw_material_label_no"),
        "food_ledger_qr_raw_material",
        ["label_no"],
        unique=False,
    )
    op.create_index(
        "ix_food_ledger_qr_raw_material_source_updated_at",
        "food_ledger_qr_raw_material",
        ["source_updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_food_ledger_qr_raw_material_source_updated_at", table_name="food_ledger_qr_raw_material"
    )
    op.drop_index(
        op.f("ix_food_ledger_qr_raw_material_label_no"), table_name="food_ledger_qr_raw_material"
    )
    op.drop_index(
        op.f("ix_food_ledger_qr_raw_material_barcode_no"), table_name="food_ledger_qr_raw_material"
    )
    op.drop_table("food_ledger_qr_raw_material")
