"""bound integration_request_field audit columns and add optimistic lock version

Revision ID: 45
Revises: 44
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "45"
down_revision: str | Sequence[str] | None = "44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "integration_request_field",
        "created_by",
        existing_type=sa.String(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "integration_request_field",
        "updated_by",
        existing_type=sa.String(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.add_column(
        "integration_request_field",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("integration_request_field", "version")
    op.alter_column(
        "integration_request_field",
        "updated_by",
        existing_type=sa.String(length=50),
        type_=sa.String(),
        existing_nullable=True,
    )
    op.alter_column(
        "integration_request_field",
        "created_by",
        existing_type=sa.String(length=50),
        type_=sa.String(),
        existing_nullable=True,
    )
