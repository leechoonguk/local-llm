"""add integration request field

Revision ID: 9
Revises: 8
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9"
down_revision: str | Sequence[str] | None = "8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
        sa.Column("default_value", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("value_type", sa.String(length=20), nullable=False),
        sa.Column("format", sa.String(length=64), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("sensitive", sa.Boolean(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(value_source IN ('CALLER', 'CONTEXT') AND source_key IS NOT NULL AND literal_value IS NULL AND secret_ref IS NULL) OR (value_source = 'LITERAL' AND source_key IS NULL AND literal_value IS NOT NULL AND secret_ref IS NULL) OR (value_source = 'SECRET_REF' AND source_key IS NULL AND literal_value IS NULL AND secret_ref IS NOT NULL)",
            name="ck_integration_request_field_source",
        ),
        sa.CheckConstraint("ordinal >= 0", name="ck_integration_request_field_ordinal"),
        sa.ForeignKeyConstraint(["operation_id"], ["integration_operation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_id", "input_key", name="uq_integration_request_field_input"),
        sa.UniqueConstraint("operation_id", "location", "wire_path", name="uq_integration_request_field_wire"),
    )
    op.create_index(op.f("ix_integration_request_field_operation_id"), "integration_request_field", ["operation_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_integration_request_field_operation_id"), table_name="integration_request_field")
    op.drop_table("integration_request_field")
