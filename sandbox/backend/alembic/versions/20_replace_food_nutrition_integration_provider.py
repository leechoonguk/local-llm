"""replace mfds integration provider for new FoodNtrCpntDbInfo02 endpoint

Revision ID: 20
Revises: 19
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "20"
down_revision: str | Sequence[str] | None = "19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Stable UUIDs — identical to the original seed (12_seed_mfds_integration_provider)
# so the provider row is replaced in place (DELETE + INSERT same PK).
PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")


def upgrade() -> None:
    provider_table = table(
        "integration_provider",
        column("id", sa.Uuid()),
    )
    op.get_bind().execute(
        provider_table.delete().where(provider_table.c.id == PROVIDER_ID)
    )
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
                "base_url": "https://apis.data.go.kr",
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    provider_table = table(
        "integration_provider",
        column("id", sa.Uuid()),
    )
    op.get_bind().execute(
        provider_table.delete().where(provider_table.c.id == PROVIDER_ID)
    )
    # Restore the original provider row (base_url was the old openapi endpoint).
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
