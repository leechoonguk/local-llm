"""add food ledger haccp label table

Revision ID: 204
Revises: 203

HACCP 표기정보 원장 - our own copy of `B553748/CertImgListServiceV3`.

One row per 품목보고번호: 14,664 records, all distinct (whole feed,
2026-09-13). This is the label axis's width - the 푸드QR family knows 4,765
labels and this one 14,664 products, sharing only 56 보고 numbers.

The printed 영양표시, the two image URLs and the barcode are **not** columns
here: the seed leaves them on the wire (revision 198), because the panel
needs a parser no one can write honestly (revision 170), the photographs
have no reader, and C005 answers barcodes properly.

`allergy_names` is stored as sent - 8,484 of its 14,664 values read
`알수없음` - and the derivation is where those stop becoming rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "204"
down_revision: str | Sequence[str] | None = "203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_ledger_haccp_label",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_report_no", sa.String(length=32), nullable=False),
        sa.Column("product_kind_division", sa.String(length=120), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("raw_material_names", sa.Text(), nullable=True),
        sa.Column("allergy_names", sa.Text(), nullable=True),
        sa.Column("product_type_name", sa.String(length=120), nullable=True),
        sa.Column("product_type_state", sa.String(length=120), nullable=True),
        sa.Column("maker_name", sa.Text(), nullable=True),
        sa.Column("seller_name", sa.Text(), nullable=True),
        sa.Column("capacity_text", sa.Text(), nullable=True),
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
        op.f("ix_food_ledger_haccp_label_item_report_no"),
        "food_ledger_haccp_label",
        ["item_report_no"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_food_ledger_haccp_label_item_report_no"), table_name="food_ledger_haccp_label"
    )
    op.drop_table("food_ledger_haccp_label")
