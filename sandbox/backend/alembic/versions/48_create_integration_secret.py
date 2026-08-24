"""create integration secret table

Revision ID: 48
Revises: 47
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "48"
down_revision: str | Sequence[str] | None = "47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_secret",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=2048), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=50), nullable=True),
        sa.Column("updated_by", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["integration_provider.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", "name", name="uq_integration_secret_provider_name"),
    )
    op.create_index(
        op.f("ix_integration_secret_provider_id"), "integration_secret", ["provider_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_integration_secret_provider_id"), table_name="integration_secret")
    op.drop_table("integration_secret")
