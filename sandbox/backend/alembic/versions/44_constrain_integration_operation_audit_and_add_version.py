"""bound integration_operation audit columns and add optimistic lock version

Revision ID: 44
Revises: 43
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "44"
down_revision: str | Sequence[str] | None = "43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "integration_operation",
        "created_by",
        existing_type=sa.String(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "integration_operation",
        "updated_by",
        existing_type=sa.String(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.add_column(
        "integration_operation",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("integration_operation", "version")
    op.alter_column(
        "integration_operation",
        "updated_by",
        existing_type=sa.String(length=50),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "integration_operation",
        "created_by",
        existing_type=sa.String(length=50),
        type_=sa.String(),
        existing_nullable=True,
    )
