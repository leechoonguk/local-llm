"""add integration operation

Revision ID: 8
Revises: 7
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8"
down_revision: str | Sequence[str] | None = "7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_operation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path_template", sa.String(length=2048), nullable=False),
        sa.Column("request_media_type", sa.String(length=120), nullable=True),
        sa.Column("connect_timeout_ms", sa.Integer(), nullable=False),
        sa.Column("read_timeout_ms", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("retry_base_ms", sa.Integer(), nullable=False),
        sa.Column("retry_max_ms", sa.Integer(), nullable=False),
        sa.Column("idempotent", sa.Boolean(), nullable=False),
        sa.Column("request_schema", sa.JSON(), nullable=True),
        sa.Column("response_schema", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("connect_timeout_ms > 0", name="ck_integration_operation_connect_timeout"),
        sa.CheckConstraint("max_retries >= 0", name="ck_integration_operation_max_retries"),
        sa.CheckConstraint("read_timeout_ms >= connect_timeout_ms", name="ck_integration_operation_read_timeout"),
        sa.CheckConstraint("retry_base_ms > 0", name="ck_integration_operation_retry_base"),
        sa.CheckConstraint("retry_max_ms >= retry_base_ms", name="ck_integration_operation_retry_max"),
        sa.ForeignKeyConstraint(["provider_id"], ["integration_provider.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", "code", name="uq_integration_operation_provider_code"),
    )
    op.create_index(op.f("ix_integration_operation_provider_id"), "integration_operation", ["provider_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_integration_operation_provider_id"), table_name="integration_operation")
    op.drop_table("integration_operation")
