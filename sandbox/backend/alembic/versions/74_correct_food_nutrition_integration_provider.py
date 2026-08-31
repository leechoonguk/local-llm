"""correct mfds integration provider display name

Revision ID: 74
Revises: 73
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "74"
down_revision: str | Sequence[str] | None = "73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The UUID every food-nutrition revision has used since 12, so the row is
# updated in place. A provider `_replace_` deletes it first, and
# `integration_operation.provider_id` is ON DELETE CASCADE - the replace at
# revision 20 is exactly what erased `search-domestic-food-products`. The seed
# string keeps its historical spelling because it is the primary key: thirty
# revisions derive ids from it, and none of them may move.
PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")

# The row's identity columns named three different things, and two of them named
# the wrong kind of thing:
#
#   code         mfds-food-nutrition          식품의약품안전처 + a dataset
#   base_url     https://apis.data.go.kr      공공데이터포털
#   display_name 식품안전나라 식품영양성분DB   <- the *other* portal + a dataset
#
# 식품안전나라 is `openapi.foodsafetykorea.go.kr`, seeded at revision 64 as
# `mfds-food-safety-korea`. Measured cost of that disagreement: the display name
# was read as the portal, so this provider's `service-key` was sent to
# foodsafetykorea, which answered `INFO-100 인증키가 유효하지 않습니다`.
#
# A provider is a **portal**: one host and one credential. The dataset is the
# endpoint - `search-food-nutrition` on `/1471000/FoodNtrCpntDbInfo02/…` already
# names it, and the sibling portal carries four such operations under one row.
# Carrying `식품영양성분DB` in the provider left no room for the portal's second
# dataset except a duplicate provider row with the same key in it. So the row
# now says only what the `base_url` is: 공공데이터포털 / `data-go-kr`.
CODE = "data-go-kr"
DISPLAY_NAME = "공공데이터포털"
PREVIOUS_CODE = "mfds-food-nutrition"
PREVIOUS_DISPLAY_NAME = "식품안전나라 식품영양성분DB"


def _provider_table():
    return table(
        "integration_provider",
        column("id", sa.Uuid()),
        column("code", sa.String()),
        column("display_name", sa.String()),
        column("updated_by", sa.String()),
    )


def _set_identity(code: str, display_name: str) -> None:
    provider = _provider_table()
    op.get_bind().execute(
        provider.update()
        .where(provider.c.id == PROVIDER_ID)
        .values(code=code, display_name=display_name, updated_by="migration")
    )


def upgrade() -> None:
    _set_identity(CODE, DISPLAY_NAME)


def downgrade() -> None:
    _set_identity(PREVIOUS_CODE, PREVIOUS_DISPLAY_NAME)
