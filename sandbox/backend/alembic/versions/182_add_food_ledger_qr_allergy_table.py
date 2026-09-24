"""add food ledger qr allergy table

Revision ID: 182
Revises: 181

The 푸드QR 알레르기정보 ledger: one row per declared allergen, 8,580 of them over
1,746 라벨 (whole feed, 2026-09-12). The pair (라벨관리번호, 일련번호) is the
unique constraint; the allergen name is 22 characters at the widest
(`조개류(굴,홍합,꼬막 포함)`) and is indexed because it is what a reader filters
on.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "182"
down_revision: str | Sequence[str] | None = "181"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_ledger_qr_allergy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label_no", sa.String(length=32), nullable=False),
        sa.Column("allergen_serial", sa.String(length=32), nullable=False),
        sa.Column("allergen_name", sa.String(length=120), nullable=True),
        sa.Column("item_report_serial", sa.String(length=32), nullable=True),
        sa.Column("barcode_no", sa.String(length=32), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("label_group_name", sa.Text(), nullable=True),
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
            "label_no", "allergen_serial", name="uq_food_ledger_qr_allergy_natural_key"
        ),
    )
    op.create_index(
        op.f("ix_food_ledger_qr_allergy_allergen_name"),
        "food_ledger_qr_allergy",
        ["allergen_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_qr_allergy_barcode_no"),
        "food_ledger_qr_allergy",
        ["barcode_no"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_qr_allergy_label_no"),
        "food_ledger_qr_allergy",
        ["label_no"],
        unique=False,
    )
    op.create_index(
        "ix_food_ledger_qr_allergy_source_updated_at",
        "food_ledger_qr_allergy",
        ["source_updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_food_ledger_qr_allergy_source_updated_at", table_name="food_ledger_qr_allergy"
    )
    op.drop_index(op.f("ix_food_ledger_qr_allergy_label_no"), table_name="food_ledger_qr_allergy")
    op.drop_index(op.f("ix_food_ledger_qr_allergy_barcode_no"), table_name="food_ledger_qr_allergy")
    op.drop_index(
        op.f("ix_food_ledger_qr_allergy_allergen_name"), table_name="food_ledger_qr_allergy"
    )
    op.drop_table("food_ledger_qr_allergy")
