"""add food ledger barcode table

Revision ID: 166
Revises: 165

The ledger `search-barcode-product-info` (revision 163) fills: one row per
(유통바코드, 품목보고번호) pair, 246,195 of them over the whole feed's 259,669
records (2026-09-12). The pair is the unique constraint because neither half
is unique on its own - 229,040 barcodes against 149,006 품목보고번호 - and
the column bounds are that walk's maxima (바코드 27, 품목보고번호 16, 식품
유형 55, 업종 12, 주소 15), with 제품명/제조사명/소비기한 as `Text`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "166"
down_revision: str | Sequence[str] | None = "165"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_ledger_barcode",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("barcode_no", sa.String(length=32), nullable=False),
        sa.Column("item_report_no", sa.String(length=32), nullable=False),
        sa.Column("permit_date", sa.String(length=20), nullable=True),
        sa.Column("production_end_date", sa.String(length=20), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("shelf_life", sa.Text(), nullable=True),
        sa.Column("product_type_name", sa.String(length=120), nullable=True),
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("industry_name", sa.String(length=120), nullable=True),
        sa.Column("site_address", sa.String(length=120), nullable=True),
        sa.Column("closed_business_date", sa.String(length=20), nullable=True),
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
            "barcode_no", "item_report_no", name="uq_food_ledger_barcode_natural_key"
        ),
    )
    op.create_index(
        op.f("ix_food_ledger_barcode_barcode_no"),
        "food_ledger_barcode",
        ["barcode_no"],
        unique=False,
    )
    op.create_index(
        "ix_food_ledger_barcode_item_report_no",
        "food_ledger_barcode",
        ["item_report_no"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_food_ledger_barcode_item_report_no", table_name="food_ledger_barcode")
    op.drop_index(op.f("ix_food_ledger_barcode_barcode_no"), table_name="food_ledger_barcode")
    op.drop_table("food_ledger_barcode")
