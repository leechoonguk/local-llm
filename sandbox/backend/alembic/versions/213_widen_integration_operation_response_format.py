"""widen integration operation response format

Revision ID: 213
Revises: 212
Create Date: 2026-09-13 18:56:44.356265

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "213"
down_revision: str | Sequence[str] | None = "212"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("ck_integration_operation_response_format", "integration_operation", type_="check")
    op.create_check_constraint(
        "ck_integration_operation_response_format",
        "integration_operation",
        "response_format IN ('JSON', 'XML', 'HTML')",
    )
    op.drop_constraint("ck_integration_operation_response_root", "integration_operation", type_="check")
    op.create_check_constraint(
        "ck_integration_operation_response_root",
        "integration_operation",
        "response_root IS NULL OR response_format = 'HTML' OR response_root LIKE '/%'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_integration_operation_response_root", "integration_operation", type_="check")
    op.create_check_constraint(
        "ck_integration_operation_response_root",
        "integration_operation",
        "response_root IS NULL OR response_root LIKE '/%'",
    )
    op.drop_constraint("ck_integration_operation_response_format", "integration_operation", type_="check")
    op.create_check_constraint(
        "ck_integration_operation_response_format",
        "integration_operation",
        "response_format IN ('JSON', 'XML')",
    )
