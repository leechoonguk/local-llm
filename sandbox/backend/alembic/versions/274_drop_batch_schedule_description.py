"""drop batch schedule description

The column was write-only: no screen read it and no job used it, so the one
surface that held it was a dialog field nobody could see the effect of. The
schedule is code, name, cron and enabled.

Revision ID: 274
Revises: 273
Create Date: 2026-09-18 08:04:58.851825

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "274"
down_revision: str | Sequence[str] | None = "273"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("batch_schedule", "description")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "batch_schedule",
        sa.Column("description", sa.VARCHAR(length=512), autoincrement=False, nullable=True),
    )
