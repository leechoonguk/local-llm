"""bound integration_response_field audit columns and add optimistic lock version

Revision ID: 47
Revises: 46
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "47"
down_revision: str | Sequence[str] | None = "46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "integration_response_field",
        "created_by",
        existing_type=sa.String(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "integration_response_field",
        "updated_by",
        existing_type=sa.String(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.add_column(
        "integration_response_field",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("integration_response_field", "version")
    op.alter_column(
        "integration_response_field",
        "updated_by",
        existing_type=sa.String(length=50),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "integration_response_field",
        "created_by",
        existing_type=sa.String(length=50),
        type_=sa.String(),
        existing_nullable=True,
    )
