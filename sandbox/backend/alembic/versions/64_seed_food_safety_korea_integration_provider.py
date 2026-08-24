"""seed food safety korea integration provider

Revision ID: 64
Revises: 63
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "64"
down_revision: str | Sequence[str] | None = "63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 식품안전나라 OpenAPI (openapi.foodsafetykorea.go.kr) is a second portal, not a second
# service of the nutrition provider: a different host, a different key, and the key
# travels in the path instead of the query string. Sharing a provider row would share
# the credential, which would then be wrong for both.
PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
BASE_URL = "https://openapi.foodsafetykorea.go.kr"


def _provider_table():
    return table(
        "integration_provider",
        column("id", sa.Uuid()),
        column("code", sa.String()),
        column("display_name", sa.String()),
        column("base_url", sa.String()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def upgrade() -> None:
    provider = _provider_table()
    op.bulk_insert(
        provider,
        [
            {
                "id": PROVIDER_ID,
                "code": "mfds-food-safety-korea",
                "display_name": "식품안전나라 OpenAPI",
                "base_url": BASE_URL,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    provider = _provider_table()
    op.get_bind().execute(provider.delete().where(provider.c.id == PROVIDER_ID))
