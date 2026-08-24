"""add description to integration response field

Revision ID: 25
Revises: 24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "25"
down_revision: str | Sequence[str] | None = "24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "integration_response_field",
        sa.Column("description", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("integration_response_field", "description")
