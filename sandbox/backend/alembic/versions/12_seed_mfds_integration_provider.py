"""seed 식품안전나라 integration provider

Revision ID: 12
Revises: 11
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "12"
down_revision: str | Sequence[str] | None = "11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")


def upgrade() -> None:
    provider = table(
        "integration_provider",
        column("id", sa.Uuid()),
        column("code", sa.String()),
        column("display_name", sa.String()),
        column("base_url", sa.String()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )
    op.bulk_insert(
        provider,
        [
            {
                "id": PROVIDER_ID,
                "code": "mfds-food-nutrition",
                "display_name": "식품안전나라 식품영양성분DB",
                "base_url": "https://openapi.foodsafetykorea.go.kr",
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM integration_provider WHERE id = :id"), {"id": PROVIDER_ID}
    )
