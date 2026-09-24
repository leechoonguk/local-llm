"""drop food ledger haccp label table

Revision ID: 172
Revises: 171

The ledger the two dropped derivations read. The feed itself is retired in
revisions 173 (fields) and 174 (operation); this is the table it filled -
14,666 records of free text whose splits are documented in revisions 170 and
171.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "172"
down_revision: str | Sequence[str] | None = "171"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_food_ledger_haccp_label_item_report_no"), table_name="food_ledger_haccp_label"
    )
    op.drop_index(
        op.f("ix_food_ledger_haccp_label_product_type_name"), table_name="food_ledger_haccp_label"
    )
    op.drop_table("food_ledger_haccp_label")


def downgrade() -> None:
    op.create_table(
        "food_ledger_haccp_label",
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("item_report_no", sa.VARCHAR(length=32), autoincrement=False, nullable=False),
        sa.Column(
            "product_kind_division", sa.VARCHAR(length=120), autoincrement=False, nullable=True
        ),
        sa.Column("product_name", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("raw_material_names", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("allergy_names", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("nutrient_text", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("barcode_numbers", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("product_type_name", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column("product_type_state", sa.VARCHAR(length=120), autoincrement=False, nullable=True),
        sa.Column("maker_name", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("seller_name", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("capacity_text", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("product_image_url", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("label_image_url", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("created_by", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column("updated_by", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.INTEGER(),
            server_default=sa.text("1"),
            autoincrement=False,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("food_ledger_haccp_label_pkey")),
    )
    op.create_index(
        op.f("ix_food_ledger_haccp_label_product_type_name"),
        "food_ledger_haccp_label",
        ["product_type_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_ledger_haccp_label_item_report_no"),
        "food_ledger_haccp_label",
        ["item_report_no"],
        unique=True,
    )
