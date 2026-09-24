"""widen food item report kind

Revision ID: 243
Revises: 242
Create Date: 2026-09-15

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "243"
down_revision: str | Sequence[str] | None = "242"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "food_item_report",
        "report_kind",
        existing_type=sa.VARCHAR(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "food_item_report",
        "report_kind",
        existing_type=sa.String(length=32),
        type_=sa.VARCHAR(length=16),
        existing_nullable=False,
    )
