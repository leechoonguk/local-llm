"""bound batch audit columns and add optimistic lock version

Revision ID: 41
Revises: 40
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "41"
down_revision: str | Sequence[str] | None = "37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "batch", "name", existing_type=sa.String(), type_=sa.String(length=120), existing_nullable=False
    )
    op.alter_column(
        "batch",
        "description",
        existing_type=sa.String(),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
    op.alter_column(
        "batch",
        "created_by",
        existing_type=sa.String(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "batch",
        "updated_by",
        existing_type=sa.String(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.add_column(
        "batch",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("batch", "version")
    op.alter_column(
        "batch",
        "updated_by",
        existing_type=sa.String(length=50),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "batch",
        "created_by",
        existing_type=sa.String(length=50),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "batch",
        "description",
        existing_type=sa.String(length=512),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "batch", "name", existing_type=sa.String(length=120), type_=sa.String(), existing_nullable=False
    )
