"""add description to integration request field

Revision ID: 24
Revises: 23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24"
down_revision: str | Sequence[str] | None = "23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "integration_request_field",
        sa.Column("description", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("integration_request_field", "description")