"""add secret_value to integration request field

Revision ID: 19
Revises: 18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "19"
down_revision: str | Sequence[str] | None = "18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "integration_request_field",
        sa.Column("secret_value", sa.String(length=2048), nullable=True),
    )
    op.drop_constraint(
        "ck_integration_request_field_source",
        "integration_request_field",
        type_="check",
    )
    op.create_check_constraint(
        "ck_integration_request_field_source",
        "integration_request_field",
        "(value_source IN ('CALLER', 'CONTEXT') AND source_key IS NOT NULL "
        "AND literal_value IS NULL AND secret_ref IS NULL AND secret_value IS NULL) "
        "OR (value_source = 'LITERAL' AND source_key IS NULL "
        "AND literal_value IS NOT NULL AND secret_ref IS NULL AND secret_value IS NULL) "
        "OR (value_source = 'SECRET_REF' AND source_key IS NULL "
        "AND literal_value IS NULL AND secret_ref IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_integration_request_field_source",
        "integration_request_field",
        type_="check",
    )
    op.create_check_constraint(
        "ck_integration_request_field_source",
        "integration_request_field",
        "(value_source IN ('CALLER', 'CONTEXT') AND source_key IS NOT NULL "
        "AND literal_value IS NULL AND secret_ref IS NULL) "
        "OR (value_source = 'LITERAL' AND source_key IS NULL "
        "AND literal_value IS NOT NULL AND secret_ref IS NULL) "
        "OR (value_source = 'SECRET_REF' AND source_key IS NULL "
        "AND literal_value IS NULL AND secret_ref IS NOT NULL)",
    )
    op.drop_column("integration_request_field", "secret_value")
