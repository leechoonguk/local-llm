"""seed food admin disposition integration operation

Revision ID: 275
Revises: 274

행정처분결과(식품제조가공업) - service I0480 on 식품안전나라. One row per
administrative disposition of a food manufacturing business: which business, the
law it broke, what the violation was, the disposition and the days it runs.

The **business** is the subject, not a product: there is no 품목보고번호 and no
제품명 among the columns, so this feed answers "is the maker of this product
under a disposition", never "what happened to this product". The join is
`LCNS_NO` (인허가번호), which `food_item_report` carries on 1,688,015 of its
1,980,742 rows (85.2 %).

Read from the portal's own page (`openApiInfo.do?…&svc_no=I2630`, the sibling
service of the same family, 2026-09-18): the URL shape, the required five and the
three optional filters. 17 output columns documented there, 17 measured here,
none missing, none extra.

Measured 2026-09-18 21:5x KST (the 09-19 KST refusal window is closed then):

    window 1/100              INFO-000  total_count 251  rows 100
    window 201/300            INFO-000  rows 51            (the short page = the end)
    window 1/500              INFO-000  rows 251           (and it resizes)
    window 1/1000             INFO-000  rows 251           (the portal's cap holds)
    window 300/399            INFO-200  해당하는 데이터가 없습니다
    window 0/5                ERROR-331 요청시작위치 값을 확인하십시오
    window inverted 5/1       ERROR-334 종료위치보다 시작위치가 더 큽니다
    an invalid key            INFO-100  (HTTP 200 - so the envelope is checked)
    /LCNS_NO=20140506502      total_count 1     (a path segment filters)
    ?LCNS_NO=20140506502      total_count 251   (a query string is ignored)
    /DSPS_DCSNDT=20260918     total_count 1
    /CHNG_DT=20260901         ERROR-303 ; =20991231 INFO-200 ; 2026-09-01 ERROR-302
    /NOSUCH=x                 total_count 251   (an unknown parameter is ignored)
    the natural key           `DSPSDTLS_SEQ` alone: 251 of 251 distinct. (The
                              data.go.kr mirror of the same dataset - 254 rows -
                              carries three duplicates; this portal does not.)
    the column maxima         VILTCN 623, LAWORD_CD_NM 137, DSPSCN 111,
                              PUBLIC_DT 21 ("2026-10-03 00:00:00.0"),
                              LAST_UPDT_DTM 23, the rest <= 22
    always empty              PRSDNT_NM and TELNO are "" on all 251 rows, so
                              neither may be `required`
    the feed's span           처분확정일자 20241002 ~ 20260918; 업종 is
                              식품제조가공업 or 식품제조가공업(주류)
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "275"
down_revision: str | Sequence[str] | None = "274"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-admin-disposition"
)

PAGE_ROOT = "/I0480/row"
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
        column("page_size", sa.Integer()),
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
                "code": "search-food-admin-disposition",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                # The portal's cap, measured: 1/1000 answered the whole feed.
                # 251 rows fit one window, so a pass is two calls - the feed and
                # the short page that ends it.
                "page_size": 1000,
                "connect_timeout_ms": 5000,
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
