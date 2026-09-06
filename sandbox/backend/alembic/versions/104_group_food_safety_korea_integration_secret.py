"""group food safety korea integration secret

Revision ID: 104
Revises: 103
Create Date: 2026-09-06

The portal's quota is per key. Measured on `search-food-item-report`
(2026-09-06): on the same window the seeded key answered `INFO-320` (hour
spent) while two freshly issued keys answered `INFO-000`, and the spent key
recovered within the hour. A pool of keys multiplies the hourly ceiling.

Only the seeded key is grouped here. The further keys are registered through
the API (`POST /integration/{id}/secrets` with the same `rotation_group`) -
issued keys are operational input, not configuration this repository owns.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision: str = "104"
down_revision: str | Sequence[str] | None = "103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROTATION_GROUP = "service-key"


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-safety-korea/{kind}")


def _secret_table():
    return table(
        "integration_secret",
        column("id", sa.Uuid()),
        column("rotation_group", sa.String()),
        column("updated_by", sa.String()),
    )


def _set_group(rotation_group: str | None) -> None:
    secret = _secret_table()
    op.get_bind().execute(
        secret.update()
        .where(secret.c.id == _id("secret:service-key"))
        .values(rotation_group=rotation_group, updated_by="migration")
    )


def upgrade() -> None:
    _set_group(ROTATION_GROUP)


def downgrade() -> None:
    _set_group(None)
