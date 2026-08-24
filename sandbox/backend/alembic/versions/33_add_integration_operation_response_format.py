"""add response_format to integration operation

Revision ID: 33
Revises: 32
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "33"
down_revision: str | Sequence[str] | None = "32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "integration_operation",
        sa.Column(
            "response_format",
            sa.String(length=8),
            nullable=False,
            server_default="JSON",
        ),
    )
    op.create_check_constraint(
        "ck_integration_operation_response_format",
        "integration_operation",
        "response_format IN ('JSON', 'XML')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_integration_operation_response_format",
        "integration_operation",
        type_="check",
    )
    op.drop_column("integration_operation", "response_format")
