"""quota food safety korea integration operation

Revision ID: 105
Revises: 104
Create Date: 2026-09-06

Two codes name the key, not the dataset, so every operation of this provider
lists them, each with the seconds the key sits out - the client tries the
next pool member on either before raising, and a job sees `IntegrationError`
only when every key is out. Measured on `search-food-item-report`
(2026-09-06): `INFO-320` ("hour's quota spent") - the seeded key answered it
on a window two fresh keys answered `INFO-000` on, and recovered within the
hour; `INFO-500` ("현재 접속 중인 인증키입니다. 잠시 후에 다시 시도하십시오")
- one key, mid-walk, with no other process, and the next key answered at
once. An hour's sit-out for a "moment" would shrink a three-key pool to one.
`INFO-300` ("유효 호출건수를 이미 초과하셨습니다") - a key's daily ceiling, met
after ~1,000 calls in a day (2026-09-06, 14:24, one key of three). When it
resets is not documented; an hour's sit-out re-asks at the cost of one call.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision: str = "105"
down_revision: str | Sequence[str] | None = "104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
QUOTA_CODES = {"INFO-320": 3600, "INFO-500": 60, "INFO-300": 3600}


def _operation_table():
    return table(
        "integration_operation",
        column("provider_id", sa.Uuid()),
        column("quota_codes", sa.JSON()),
        column("updated_by", sa.String()),
    )


def _set_quota_codes(quota_codes: dict[str, int]) -> None:
    operation = _operation_table()
    op.get_bind().execute(
        operation.update()
        .where(operation.c.provider_id == PROVIDER_ID)
        .values(quota_codes=quota_codes, updated_by="migration")
    )


def upgrade() -> None:
    _set_quota_codes(QUOTA_CODES)


def downgrade() -> None:
    _set_quota_codes({})
