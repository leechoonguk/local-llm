"""widen food item report event kind

Revision ID: 244
Revises: 243
Create Date: 2026-09-15

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "244"
down_revision: str | Sequence[str] | None = "243"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "food_item_report_event",
        "report_kind",
        existing_type=sa.VARCHAR(length=16),
        type_=sa.String(length=32),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "food_item_report_event",
        "report_kind",
        existing_type=sa.String(length=32),
        type_=sa.VARCHAR(length=16),
        existing_nullable=True,
    )
