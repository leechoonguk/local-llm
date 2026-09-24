"""seed food qr raw material integration operation

Revision ID: 193
Revises: 192

푸드QR 원재료정보 - `1471000/FoodQrInfoService02/getFoodQrProdRawmtrl02`.

What the feed is: **the 원재료명 as the package prints it**, with 함량 and 원산지 -
2,301 rows over 2,156 라벨 (whole feed, 2026-09-13).

It is not a copy of `food_item_report_ingredient` (10.1 M rows off C002/C006).
Measured on the 2,012 products both cover: this feed's text is longer on 1,985
(98.7 %), carries a percentage on 913 (45.4 %) and an origin on 1,594 (79.2 %),
where the registry split carries **zero** of either - it lists names only
(`육수, 어묵` against `연육1 44.88%[중국산/어육(갈치)…], 소맥분 24.48%(밀:미국산,
호주산)`). Mean items: 20 here, 12 there.

**The text arrives as HTML**: every one of the 2,301 rows wraps each name in a
`<a href="https://terms.naver.com/…">` link, and an origin in `<p class="bold">`.
The ledger stores what the wire sent; the derivation strips the tags, at which
point the string is the same comma-joined list the HACCP feed answers plainly.

Measured 2026-09-13: the key is (ELB_MNG_NO, RWMT_LTID_SN) - 2,301 distinct on
2,301 rows. The widest `PRVW_CN` is 15,988 characters.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "193"
down_revision: str | Sequence[str] | None = "192"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-raw-material")

PAGE_ROOT = "/body/items"
PATH_TEMPLATE = "/1471000/FoodQrInfoService02/getFoodQrProdRawmtrl02"


def _operation_table():
    return table(
        "integration_operation",
        column("id", sa.Uuid()),
        column("provider_id", sa.Uuid()),
        column("code", sa.String()),
        column("method", sa.String()),
        column("path_template", sa.String()),
        column("request_media_type", sa.String()),
        column("response_format", sa.String()),
        column("response_root", sa.String()),
        column("connect_timeout_ms", sa.Integer()),
        column("read_timeout_ms", sa.Integer()),
        column("max_retries", sa.Integer()),
        column("retry_base_ms", sa.Integer()),
        column("retry_max_ms", sa.Integer()),
        column("idempotent", sa.Boolean()),
        column("request_schema", sa.JSON(none_as_null=True)),
        column("quota_codes", sa.JSON()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def upgrade() -> None:
    op.bulk_insert(
        _operation_table(),
        [
            {
                "id": OPERATION_ID,
                "provider_id": PROVIDER_ID,
                "code": "search-food-qr-raw-material",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                "connect_timeout_ms": 5000,
                "read_timeout_ms": 10000,
                "max_retries": 2,
                "retry_base_ms": 200,
                "retry_max_ms": 1000,
                "idempotent": True,
                "request_schema": None,
                "quota_codes": {},
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
