"""constrain request field value_type to its closed value set

Revision ID: 35
Revises: 34
"""

from collections.abc import Sequence

from alembic import op

revision: str = "35"
down_revision: str | Sequence[str] | None = "34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_integration_request_field_value_type",
        "integration_request_field",
        "value_type IN ('STRING', 'INTEGER', 'NUMBER', 'BOOLEAN', 'DATE', 'DATETIME', 'JSON')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_integration_request_field_value_type", "integration_request_field", type_="check")
