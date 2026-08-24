"""drop integration_response_header table

Revision ID: 55
Revises: 54
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "55"
down_revision: str | Sequence[str] | None = "54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_integration_response_header_operation_id"), table_name="integration_response_header")
    op.drop_table("integration_response_header")


def downgrade() -> None:
    """Restore the table shape. Its rows now live in integration_field."""
    op.create_table(
        "integration_response_header",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("header_name", sa.String(length=128), nullable=False),
        sa.Column("match_mode", sa.String(length=16), nullable=False),
        sa.Column("expected_values", sa.JSON(), nullable=True),
        sa.Column("value_type", sa.String(length=24), nullable=False),
        sa.Column("result_key", sa.String(length=128), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("sensitive", sa.Boolean(), nullable=False),
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
        sa.UniqueConstraint(
            "operation_id", "header_name", name="uq_integration_response_header_operation_name"
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"], ["integration_operation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_response_header_operation_id"), "integration_response_header", ["operation_id"])
