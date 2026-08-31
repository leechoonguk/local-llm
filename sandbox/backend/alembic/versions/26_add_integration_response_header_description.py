"""add description to integration response header

Revision ID: 26
Revises: 25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "26"
down_revision: str | Sequence[str] | None = "25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "integration_response_header",
        sa.Column("description", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("integration_response_header", "description")