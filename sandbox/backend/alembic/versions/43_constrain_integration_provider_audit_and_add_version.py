"""bound integration_provider audit columns and add optimistic lock version

Revision ID: 43
Revises: 42
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "43"
down_revision: str | Sequence[str] | None = "42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "integration_provider",
        "created_by",
        existing_type=sa.String(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "integration_provider",
        "updated_by",
        existing_type=sa.String(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.add_column(
        "integration_provider",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("integration_provider", "version")
    op.alter_column(
        "integration_provider",
        "updated_by",
        existing_type=sa.String(length=50),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "integration_provider",
        "created_by",
        existing_type=sa.String(length=50),
        type_=sa.String(),
        existing_nullable=True,
    )
