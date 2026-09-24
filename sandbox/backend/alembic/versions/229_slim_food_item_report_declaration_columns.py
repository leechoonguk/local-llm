"""slim food item report declaration columns

Revision ID: 229
Revises: 228
Create Date: 2026-09-14

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "229"
down_revision: str | Sequence[str] | None = "228"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    for column in (
        "importer_name",
        "product_name",
        "product_name_en",
        "overseas_maker_name",
        "origin_country",
        "expiry_text",
    ):
        op.drop_column("food_item_report_declaration", column)


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "food_item_report_declaration", sa.Column("importer_name", sa.Text(), nullable=True)
    )
    op.add_column(
        "food_item_report_declaration", sa.Column("product_name", sa.Text(), nullable=True)
    )
    op.add_column(
        "food_item_report_declaration", sa.Column("product_name_en", sa.Text(), nullable=True)
    )
    op.add_column(
        "food_item_report_declaration", sa.Column("overseas_maker_name", sa.Text(), nullable=True)
    )
    op.add_column(
        "food_item_report_declaration",
        sa.Column("origin_country", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "food_item_report_declaration",
        sa.Column("expiry_text", sa.String(length=40), nullable=True),
    )
