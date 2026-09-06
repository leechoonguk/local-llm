"""add integration call secret name

Revision ID: 103
Revises: 102
Create Date: 2026-09-06

Which named credential a call went out with. The name only - the value is
scrubbed from the log as before. With a pool, "which key hit the quota" is a
question the call log has to answer.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "103"
down_revision: str | Sequence[str] | None = "102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("integration_call", sa.Column("secret_name", sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("integration_call", "secret_name")
