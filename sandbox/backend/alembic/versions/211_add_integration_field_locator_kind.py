"""add integration field locator kind

Revision ID: 211
Revises: 210
Create Date: 2026-09-13 18:56:44.356265

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "211"
down_revision: str | Sequence[str] | None = "210"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "integration_field",
        sa.Column("locator_kind", sa.String(length=16), server_default="POINTER", nullable=False),
    )
    op.create_check_constraint(
        "ck_integration_field_locator_kind",
        "integration_field",
        "locator_kind IN ('POINTER', 'CSS', 'LABEL', 'REGEX')",
    )
    op.create_check_constraint(
        "ck_integration_field_locator_direction",
        "integration_field",
        "direction = 'RESPONSE' OR locator_kind = 'POINTER'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_integration_field_locator_direction", "integration_field", type_="check")
    op.drop_constraint("ck_integration_field_locator_kind", "integration_field", type_="check")
    op.drop_column("integration_field", "locator_kind")
