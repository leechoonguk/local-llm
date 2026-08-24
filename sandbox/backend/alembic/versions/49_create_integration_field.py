"""create integration field table

Revision ID: 49
Revises: 48
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "49"
down_revision: str | Sequence[str] | None = "48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_field",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("location", sa.String(length=10), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("wire_path", sa.String(length=512), nullable=False),
        sa.Column("value_source", sa.String(length=16), nullable=True),
        sa.Column("value", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("secret_id", sa.Uuid(), nullable=True),
        sa.Column("value_type", sa.String(length=20), nullable=False),
        sa.Column("format", sa.String(length=64), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("sensitive", sa.Boolean(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("match_mode", sa.String(length=16), nullable=True),
        sa.Column("expected_values", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_by", sa.String(length=50), nullable=True),
        sa.Column("updated_by", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint("ordinal >= 0", name="ck_integration_field_ordinal"),
        sa.CheckConstraint(
            "direction IN ('REQUEST', 'RESPONSE')", name="ck_integration_field_direction"
        ),
        sa.CheckConstraint(
            "location IN ('PATH', 'QUERY', 'HEADER', 'BODY')",
            name="ck_integration_field_location",
        ),
        sa.CheckConstraint(
            "value_type IN ('STRING', 'INTEGER', 'NUMBER', 'BOOLEAN', 'DATE', 'DATETIME', "
            "'JSON', 'EPOCH_SECONDS', 'HTTP_DATE', 'DURATION_SECONDS')",
            name="ck_integration_field_value_type",
        ),
        sa.CheckConstraint(
            "value_type NOT IN ('EPOCH_SECONDS', 'HTTP_DATE', 'DURATION_SECONDS') "
            "OR location = 'HEADER'",
            name="ck_integration_field_header_value_type",
        ),
        sa.CheckConstraint(
            "(direction = 'REQUEST' AND value_source IS NOT NULL) "
            "OR (direction = 'RESPONSE' AND value_source IS NULL)",
            name="ck_integration_field_value_source_direction",
        ),
        sa.CheckConstraint(
            "value_source IS NULL OR value_source IN ('CALLER', 'LITERAL', 'SECRET', 'CONTEXT')",
            name="ck_integration_field_value_source",
        ),
        sa.CheckConstraint(
            "(value_source = 'SECRET' AND secret_id IS NOT NULL) "
            "OR (value_source IS DISTINCT FROM 'SECRET' AND secret_id IS NULL)",
            name="ck_integration_field_secret",
        ),
        sa.CheckConstraint(
            "value_source IS DISTINCT FROM 'LITERAL' OR value IS NOT NULL",
            name="ck_integration_field_literal_value",
        ),
        sa.CheckConstraint(
            "(match_mode IS NULL AND expected_values IS NULL) "
            "OR (direction = 'RESPONSE' AND location = 'HEADER')",
            name="ck_integration_field_match_direction",
        ),
        sa.CheckConstraint(
            "match_mode IS NULL OR match_mode IN ('IGNORE', 'PRESENT', 'EXACT', 'ONE_OF')",
            name="ck_integration_field_match_mode",
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"], ["integration_operation.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["secret_id"], ["integration_secret.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_id", "direction", "key", name="uq_integration_field_key"),
        sa.UniqueConstraint(
            "operation_id", "direction", "location", "wire_path", name="uq_integration_field_wire"
        ),
    )
    op.create_index(op.f("ix_integration_field_operation_id"), "integration_field", ["operation_id"])
    op.create_index(op.f("ix_integration_field_secret_id"), "integration_field", ["secret_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_integration_field_secret_id"), table_name="integration_field")
    op.drop_index(op.f("ix_integration_field_operation_id"), table_name="integration_field")
    op.drop_table("integration_field")
