"""add integration operation quota codes

Revision ID: 102
Revises: 101
Create Date: 2026-09-06

The envelope values that mean "not this credential right now" rather than
"this answer is wrong", each with the seconds the key sits out. The client
rotates to the next pool member on one of these before it raises; an empty
object is a provider without per-key state.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "102"
down_revision: str | Sequence[str] | None = "101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "integration_operation",
        sa.Column("quota_codes", sa.JSON(), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("integration_operation", "quota_codes")
