"""bound user audit columns and add optimistic lock version

Revision ID: 42
Revises: 41
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "42"
down_revision: str | Sequence[str] | None = "41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "user",
        "created_by",
        existing_type=sa.String(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "user",
        "updated_by",
        existing_type=sa.String(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.add_column(
        "user",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user", "version")
    op.alter_column(
        "user",
        "updated_by",
        existing_type=sa.String(length=50),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "user",
        "created_by",
        existing_type=sa.String(length=50),
        type_=sa.String(),
        existing_nullable=True,
    )
