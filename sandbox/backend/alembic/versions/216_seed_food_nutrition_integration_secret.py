"""seed data go kr import food integration secret

Revision ID: 216
Revises: 215

The 수입식품 services of this gateway answer a **different** account's key than
the one revision 12 seeded: measured 2026-09-13, the seeded key answers
`SERVICE_KEY_IS_NOT_REGISTERED_ERROR` on
`IprtFoodPrdtKoreanLabelingText` while this one answers `NORMAL SERVICE.` - a
data.go.kr key carries the datasets its account applied for, and this account
holds the seven 수입식품 datasets.

A pool is not what this is (no `rotation_group`): the two keys are not
interchangeable, they are two different subscriptions of one gateway, and a
field names the one its dataset was approved under.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "216"
down_revision: str | Sequence[str] | None = "215"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/secret:service-key-import-food")
SECRET_NAME = "service-key-import-food"
SECRET_VALUE = "6782fd7d176ca2543b0c66af80f2d2a0ce9c0ef47fd7181efe39c9add394abac"


def _secret_table() -> sa.TableClause:
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
    op.bulk_insert(
        _secret_table(),
        [
            {
                "id": SECRET_ID,
                "provider_id": PROVIDER_ID,
                "name": SECRET_NAME,
                "value": SECRET_VALUE,
                "description": "공공데이터포털 인증키 — 수입식품 계열 데이터셋 7종이 승인된 계정의 키",
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    secret = _secret_table()
    op.get_bind().execute(secret.delete().where(secret.c.id == SECRET_ID))
