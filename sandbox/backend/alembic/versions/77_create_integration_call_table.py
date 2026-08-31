"""create integration call table

Revision ID: 77
Revises: 76
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "77"
down_revision: str | Sequence[str] | None = "76"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # One row per executed external call. `operation_id` is SET NULL and the codes
    # are stored as strings because a `_replace_` revision deletes the operation
    # row: the log has to outlive the configuration it used.
    op.create_table(
        "integration_call",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=True),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("operation_code", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("request_headers", sa.JSON(), nullable=False),
        sa.Column("request_body", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_headers", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.String(length=512), nullable=True),
        sa.Column("created_by", sa.String(length=50), nullable=True),
        sa.Column("updated_by", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "(outcome IN ('TIMEOUT', 'UNREACHABLE') AND status_code IS NULL) OR (outcome NOT IN ('TIMEOUT', 'UNREACHABLE') AND status_code IS NOT NULL)",
            name="ck_integration_call_answered",
        ),
        sa.CheckConstraint(
            "method IN ('GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE')",
            name="ck_integration_call_method",
        ),
        sa.CheckConstraint(
            "outcome IN ('SUCCESS', 'REFUSED', 'TIMEOUT', 'UNREACHABLE', 'RATE_LIMITED')",
            name="ck_integration_call_outcome",
        ),
        sa.CheckConstraint("attempts >= 1", name="ck_integration_call_attempts"),
        sa.CheckConstraint("duration_ms >= 0", name="ck_integration_call_duration"),
        sa.CheckConstraint(
            "status_code IS NULL OR (status_code BETWEEN 100 AND 599)",
            name="ck_integration_call_status_code",
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"], ["integration_operation.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_integration_call_operation_id"), "integration_call", ["operation_id"], unique=False
    )
    op.create_index(
        "ix_integration_call_provider_code_created_at",
        "integration_call",
        ["provider_code", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_integration_call_request_id"), "integration_call", ["request_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_integration_call_request_id"), table_name="integration_call")
    op.drop_index("ix_integration_call_provider_code_created_at", table_name="integration_call")
    op.drop_index(op.f("ix_integration_call_operation_id"), table_name="integration_call")
    op.drop_table("integration_call")
