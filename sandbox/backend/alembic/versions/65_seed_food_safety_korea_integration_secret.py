"""seed food safety korea integration secret

Revision ID: 65
Revises: 64
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "65"
down_revision: str | Sequence[str] | None = "64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")

# The portal issues its own key, and it travels as a **path segment**
# (/api/{key}/I1250/json/1/5) rather than a query parameter — which is why the field
# that carries it is a PATH row with value_source SECRET.
SERVICE_KEY = "7d59300f145b402a8b48"


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-safety-korea/{kind}")


def _secret_table():
    return table(
        "integration_secret",
        column("id", sa.Uuid()),
        column("provider_id", sa.Uuid()),
        column("name", sa.String()),
        column("value", sa.String()),
        column("description", sa.String()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def upgrade() -> None:
    secret = _secret_table()
    op.bulk_insert(
        secret,
        [
            {
                "id": _id("secret:service-key"),
                "provider_id": PROVIDER_ID,
                "name": "service-key",
                "value": SERVICE_KEY,
                "description": "식품안전나라 OpenAPI 에서 발급된 인증키 (경로 세그먼트로 전달)",
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    secret = _secret_table()
    op.get_bind().execute(secret.delete().where(secret.c.provider_id == PROVIDER_ID))
