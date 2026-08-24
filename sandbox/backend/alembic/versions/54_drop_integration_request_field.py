"""drop integration_request_field table

Revision ID: 54
Revises: 53
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "54"
down_revision: str | Sequence[str] | None = "53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_integration_request_field_operation_id"), table_name="integration_request_field")
    op.drop_table("integration_request_field")


def downgrade() -> None:
    """Restore the table shape. Its rows now live in integration_field."""
    op.create_table(
        "integration_request_field",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("input_key", sa.String(length=128), nullable=False),
        sa.Column("location", sa.String(length=10), nullable=False),
        sa.Column("wire_path", sa.String(length=512), nullable=False),
        sa.Column("value_source", sa.String(length=16), nullable=False),
        sa.Column("source_key", sa.String(length=256), nullable=True),
        sa.Column("literal_value", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("secret_ref", sa.String(length=512), nullable=True),
        sa.Column("secret_value", sa.String(length=2048), nullable=True),
        sa.Column("default_value", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("value_type", sa.String(length=20), nullable=False),
        sa.Column("format", sa.String(length=64), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("sensitive", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint("ordinal >= 0", name="ck_integration_request_field_ordinal"),
        sa.UniqueConstraint(
            "operation_id", "location", "wire_path", name="uq_integration_request_field_wire"
        ),
        sa.UniqueConstraint(
            "operation_id", "input_key", name="uq_integration_request_field_input"
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"], ["integration_operation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_request_field_operation_id"), "integration_request_field", ["operation_id"])
