"""drop food barcode ledger

Revision ID: 120
Revises: 119
Create Date: 2026-09-07 09:40:00.000000

The last of three: the feed's fields went at 118 and its operation at 119;
this drops the ledger they filled (`barcode`, revision 81, renamed
`food_barcode` at 91). The 53,242 rows it held were the portal's 2015
snapshot and are recoverable from nowhere newer - see revision 118.

The downgrade recreates the table as revision 91 left it: the same columns,
the same unique constraint and index names, empty. Postgres keeps the primary
key's name (`barcode_pkey`) through the rename at 91, so the downgrade names
it explicitly rather than letting `create_table` derive `food_barcode_pkey`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "120"
down_revision: str | Sequence[str] | None = "119"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("ix_food_barcode_source_updated_at", table_name="food_barcode")
    op.drop_index("ix_food_barcode_report_no", table_name="food_barcode")
    op.drop_table("food_barcode")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "food_barcode",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("barcode_no", sa.String(length=32), nullable=False),
        sa.Column("report_no", sa.String(length=50), nullable=False),
        sa.Column("report_item_name", sa.String(length=200), nullable=True),
        sa.Column("product_name", sa.String(length=200), nullable=True),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("upper_product_classification_name", sa.String(length=120), nullable=True),
        sa.Column("top_product_classification_name", sa.String(length=120), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="barcode_pkey"),
        sa.UniqueConstraint("barcode_no", "report_no", name="uq_food_barcode_barcode_no_report_no"),
    )
    op.create_index("ix_food_barcode_report_no", "food_barcode", ["report_no"], unique=False)
    op.create_index(
        "ix_food_barcode_source_updated_at", "food_barcode", ["source_updated_at"], unique=False
    )
