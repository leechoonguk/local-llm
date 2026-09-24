"""replace food nutrition integration secret

Revision ID: 162
Revises: 161

The portal re-issued this provider's key, and the new one reaches further
than the one revision 52 seeded. Measured 2026-09-12, same account:

    /1471000/FoodNtrCpntDbInfo02   old key  resultCode 00, totalCount 319060
                                   new key  resultCode 00, totalCount 319060
    /B553748/CertImgListServiceV3  old key  HTTP 403 SERVICE_KEY_IS_NOT_REGISTERED_ERROR (30)
                                   new key  resultCode OK, totalCount 14666

So `search-haccp-label` (revision 160) needs no credential of its own: a
provider is a host and its named secret is the credential every operation
under it sends, and this account's approvals now cover both agencies behind
`apis.data.go.kr`. A second named row would have stored one key twice and
left two places to rotate it.

An UPDATE rather than a delete-and-insert: `integration_field.secret_id`
points at this row from both operations, so replacing the row would have to
take their key fields with it and put them back.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "162"
down_revision: str | Sequence[str] | None = "161"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/secret:service-key")

# What the account holds now, and what revision 52 seeded.
SERVICE_KEY = "6782fd7d176ca2543b0c66af80f2d2a0ce9c0ef47fd7181efe39c9add394abac"
PREVIOUS_SERVICE_KEY = "725c89cee973af7c02141ae7ef8f0001f025ac0a24d9766afbb101c8b25fcb4b"

DESCRIPTION = (
    "공공데이터포털 OpenAPI 에서 발급된 인증키 — 이 계정이 승인받은 서비스 전체"
    " (1471000 식품영양성분DB, B553748 HACCP 표기정보)"
)
# Revision 52's own wording, so a downgrade puts the row back as it stood.
PREVIOUS_DESCRIPTION = "공공데이터포털에서 발급 받은 인증키 (URL Encode)"


def _secret_table():
    return table(
        "integration_secret",
        column("id", sa.Uuid()),
        column("value", sa.String()),
        column("description", sa.String()),
        column("updated_by", sa.String()),
    )


def _set(value: str, description: str) -> None:
    secret = _secret_table()
    op.get_bind().execute(
        secret.update()
        .where(secret.c.id == SECRET_ID)
        .values(value=value, description=description, updated_by="migration")
    )


def upgrade() -> None:
    _set(SERVICE_KEY, DESCRIPTION)


def downgrade() -> None:
    _set(PREVIOUS_SERVICE_KEY, PREVIOUS_DESCRIPTION)
