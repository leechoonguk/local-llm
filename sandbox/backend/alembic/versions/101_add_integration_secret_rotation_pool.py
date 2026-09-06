"""add integration secret rotation pool

Revision ID: 101
Revises: 100
Create Date: 2026-09-06

Secrets of one provider that share a `rotation_group` are one credential
to the caller: the client sends whichever member is not spent. `exhausted_until`
is when a member answered the operation's quota code, plus the portal's window
- measured on mfds-food-safety-korea (2026-09-06): the quota is per key
(one key INFO-320, two fresh keys INFO-000 on the same window) and resets
within the hour.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "101"
down_revision: str | Sequence[str] | None = "100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "integration_secret", sa.Column("rotation_group", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "integration_secret",
        sa.Column("exhausted_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("integration_secret", "exhausted_until")
    op.drop_column("integration_secret", "rotation_group")
