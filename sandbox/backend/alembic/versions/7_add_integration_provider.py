"""add integration provider

Revision ID: 7
Revises: 6
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7"
down_revision: str | Sequence[str] | None = "6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_provider",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_integration_provider_code"),
    )
    op.create_index(op.f("ix_integration_provider_code"), "integration_provider", ["code"])


def downgrade() -> None:
    op.drop_index(op.f("ix_integration_provider_code"), table_name="integration_provider")
    op.drop_table("integration_provider")
