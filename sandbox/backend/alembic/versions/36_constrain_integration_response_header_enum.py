"""constrain response header match_mode to its closed value set

Revision ID: 36
Revises: 35
"""

from collections.abc import Sequence

from alembic import op

revision: str = "36"
down_revision: str | Sequence[str] | None = "35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_integration_response_header_match_mode",
        "integration_response_header",
        "match_mode IN ('IGNORE', 'PRESENT', 'EXACT', 'ONE_OF')",
    )
    op.create_check_constraint(
        "ck_integration_response_header_value_type",
        "integration_response_header",
        "value_type IN ('STRING', 'INTEGER', 'NUMBER', 'EPOCH_SECONDS', "
        "'HTTP_DATE', 'DURATION_SECONDS')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_integration_response_header_value_type",
        "integration_response_header",
        type_="check",
    )
    op.drop_constraint("ck_integration_response_header_match_mode", "integration_response_header", type_="check")
