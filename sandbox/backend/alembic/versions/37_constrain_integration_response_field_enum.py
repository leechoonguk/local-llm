"""constrain response field value_type to its closed value set

Revision ID: 37
Revises: 36
"""

from collections.abc import Sequence

from alembic import op

revision: str = "37"
down_revision: str | Sequence[str] | None = "36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_integration_response_field_value_type",
        "integration_response_field",
        "value_type IN ('STRING', 'INTEGER', 'NUMBER', 'BOOLEAN', 'DATE', 'DATETIME', 'JSON')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_integration_response_field_value_type", "integration_response_field", type_="check")
