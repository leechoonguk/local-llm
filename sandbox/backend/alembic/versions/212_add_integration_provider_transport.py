"""add integration provider transport

Revision ID: 212
Revises: 211
Create Date: 2026-09-13 18:56:44.356265

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "212"
down_revision: str | Sequence[str] | None = "211"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "integration_provider",
        sa.Column("transport", sa.String(length=16), server_default="HTTP_JSON", nullable=False),
    )
    op.add_column(
        "integration_provider", sa.Column("bootstrap_path", sa.String(length=512), nullable=True)
    )
    op.create_check_constraint(
        "ck_integration_provider_transport",
        "integration_provider",
        "transport IN ('HTTP_JSON', 'HTML_FORM')",
    )
    op.create_check_constraint(
        "ck_integration_provider_bootstrap",
        "integration_provider",
        "transport = 'HTML_FORM' OR bootstrap_path IS NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_integration_provider_bootstrap", "integration_provider", type_="check")
    op.drop_constraint("ck_integration_provider_transport", "integration_provider", type_="check")
    op.drop_column("integration_provider", "bootstrap_path")
    op.drop_column("integration_provider", "transport")
