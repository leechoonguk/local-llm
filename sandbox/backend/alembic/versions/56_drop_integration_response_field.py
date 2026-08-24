"""drop integration_response_field table

Revision ID: 56
Revises: 55
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "56"
down_revision: str | Sequence[str] | None = "55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_integration_response_field_operation_id"), table_name="integration_response_field")
    op.drop_table("integration_response_field")


def downgrade() -> None:
    """Restore the table shape. Its rows now live in integration_field."""
    op.create_table(
        "integration_response_field",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("source_pointer", sa.String(length=512), nullable=False),
        sa.Column("result_key", sa.String(length=128), nullable=False),
        sa.Column("value_type", sa.String(length=20), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("default_value", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("ordinal >= 0", name="ck_integration_response_field_ordinal"),
        sa.UniqueConstraint(
            "operation_id", "result_key", name="uq_integration_response_field_result"
        ),
        sa.UniqueConstraint(
            "operation_id", "source_pointer", name="uq_integration_response_field_pointer"
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"], ["integration_operation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_response_field_operation_id"), "integration_response_field", ["operation_id"])
