"""seed mfds integration secret

Revision ID: 52
Revises: 51
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "52"
down_revision: str | Sequence[str] | None = "51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")
SERVICE_KEY = "725c89cee973af7c02141ae7ef8f0001f025ac0a24d9766afbb101c8b25fcb4b"


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-nutrition/{kind}")


def upgrade() -> None:
    secret = table(
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
    op.bulk_insert(
        secret,
        [
            {
                "id": _id("secret:service-key"),
                "provider_id": PROVIDER_ID,
                "name": "service-key",
                "value": SERVICE_KEY,
                "description": "공공데이터포털에서 발급 받은 인증키 (URL Encode)",
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    secret = table("integration_secret", column("provider_id", sa.Uuid()))
    op.get_bind().execute(secret.delete().where(secret.c.provider_id == PROVIDER_ID))
