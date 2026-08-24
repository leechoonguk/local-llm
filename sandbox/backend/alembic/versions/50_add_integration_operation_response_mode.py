"""add response mode to integration operation and drop response schema

Revision ID: 50
Revises: 49
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "50"
down_revision: str | Sequence[str] | None = "49"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "integration_operation",
        sa.Column("response_mode", sa.String(length=16), server_default="MAPPED", nullable=False),
    )
    op.add_column(
        "integration_operation", sa.Column("response_root", sa.String(length=512), nullable=True)
    )
    op.create_check_constraint(
        "ck_integration_operation_response_mode",
        "integration_operation",
        "response_mode IN ('MAPPED', 'PASSTHROUGH')",
    )
    op.create_check_constraint(
        "ck_integration_operation_response_root",
        "integration_operation",
        "(response_mode = 'MAPPED' AND response_root IS NULL) "
        "OR (response_mode = 'PASSTHROUGH' AND response_root IS NOT NULL)",
    )
    op.drop_column("integration_operation", "response_schema")


def downgrade() -> None:
    op.add_column(
        "integration_operation",
        sa.Column("response_schema", sa.JSON(), server_default="{}", nullable=False),
    )
    op.drop_constraint(
        "ck_integration_operation_response_root", "integration_operation", type_="check"
    )
    op.drop_constraint(
        "ck_integration_operation_response_mode", "integration_operation", type_="check"
    )
    op.drop_column("integration_operation", "response_root")
    op.drop_column("integration_operation", "response_mode")
