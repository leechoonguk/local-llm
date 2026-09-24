"""seed barcode product info integration operation

Revision ID: 163
Revises: 162

바코드연계제품정보 - service C005 on 식품안전나라. Same portal, same key
pool, same RANGE window as every sibling of this provider.

**This is not the feed revisions 118-120 retired.** That one was I2570
(유통바코드), a 2015 snapshot: all 53,242 rows carried `LAST_UPDT_DTM`
2015-01-22 and the portal answered INFO-200 to any later `CHNG_DT`. C005 is
live - measured 2026-09-12, the tail of the feed carries 보고일자 20260630,
20260724, 20260812 and 20260821 - and it is five times the size.

What the feed is: the barcode a product is sold under, beside the
품목보고번호 it reports under. One row per (바코드, 품목보고번호) pair: a
product with several barcodes sends several rows, and the same pair repeats
where the portal carries more than one registration of it.

Measured 2026-09-12 with the project probe and a full walk:

    window at the start      INFO-000  total_count 259669, 3 rows
    window moved, resized    INFO-000  - the window moves and its size shows
    window inverted (3/1)    ERROR-334 종료위치보다 시작위치가 더 큽니다
    /CHNG_DT=20260908        INFO-000  total 7    - the filter filters
    /CHNG_DT=20240101        ERROR-303 최대 7일까지 증분 데이터만
    /CHNG_DT=2026-09-01      ERROR-302 YYYYMMDD 8자리 단일값
    /CHNG_DT=<today>         INFO-700  오늘 변경분은 19시 이후
    /NOPE=1                  INFO-000  + [안내] 지원하지 않는 요청인자
                             and the unfiltered 259,669 - an unknown filter
                             is ignored, which is why only measured filters
                             get a row

The walk is the whole feed every night, as for every ledger here; `CHNG_DT`
is seeded because the operation is a caller-facing surface too, not because
the sync uses it (rule://backend-ledger: a sync is everything).
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "163"
down_revision: str | Sequence[str] | None = "162"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-barcode-product-info"
)

PAGE_ROOT = "/C005/row"
PATH_TEMPLATE = "/api/{service_key}/{service_id}/{data_type}/{range_start}/{range_end}"
QUOTA_CODES = {"INFO-320": 3600, "INFO-500": 60, "INFO-300": 3600}


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
    operation = _operation_table()
    op.bulk_insert(
        operation,
        [
            {
                "id": OPERATION_ID,
                "provider_id": PROVIDER_ID,
                "code": "search-barcode-product-info",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                "connect_timeout_ms": 5000,
                # The portal's deep windows are slow (C002 tail 28.6 s); the
                # same margin every sibling of this provider carries.
                "read_timeout_ms": 30000,
                "max_retries": 2,
                "retry_base_ms": 200,
                "retry_max_ms": 1000,
                "idempotent": True,
                "request_schema": None,
                "quota_codes": QUOTA_CODES,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
