"""seed common standard type integration operation

Revision ID: 122
Revises: 121

공통기준종류 - service I2590 on 식품안전나라. Same portal, same key pool, same
RANGE window as I2530 (`search-test-item`); the service id and the columns
differ. The first of the four 기준규격 feeds (I2590, I2610, I2580, I2600):
this one names the 공통기준 groups (`식품의 기준 및 규격(전부개정)` and its
children) that the 공통기준규격 rows of I2600 point at through
`CMMN_SPEC_CD`.

Why this feed: `food_product_classification` says what a food is and
`food_test_item` what can be tested; neither says which tests a food type must
pass and against what limit. The 기준규격 family does - I2600 and I2580 are
one row per (food type, test item, clause) with the limit, the judgement
format and the unit; I2590 and I2610 are the group codes and the exclusions
those rows refer to.

Written from the portal's documentation on 2026-09-07 morning and measured
that evening (the C006 procedure, project probe, 20:38 KST), because the
family is closed by day:

    every I25xx/I26xx call, 09:00-19:00 KST  ERROR-503 "09시~19시에는 서비스가 제한됩니다"
    (key and `api/sample/` alike)

    window 1/3            INFO-000  total_count 90   rows 3   0.4 s
    window inverted 3/1   ERROR-334 "종료위치보다 시작위치가 더 큽니다"
    tail 89/100           INFO-000  rows 2   0.4 s  (read_timeout_ms below)
    one past, 91/92       INFO-200 "해당하는 데이터가 없습니다" (the walk's end-of-feed reading)
    /LAST_UPDT_DTM=20260901   INFO-200 (no row this week); =20260801 ERROR-303
                          "호출일자 기준 최대 7일까지 증분 데이터만 호출할 수 있습니다" -
                          the filter reaches back 7 days, so the nightly pass
                          stays positional (`app/batch/sync_mfds_ledgers.py`)
    an unsupported key    INFO-000 "[안내] … 사용 가능한 요청인자: LAST_UPDT_DTM"
    whole feed            90 rows in one window; `CMMN_SPEC_CD` unique, never
                          empty; `HRNK_CMMN_SPEC_CD` empty on the 3 roots; LV 1-8

The envelope shape (`/I2590/RESULT/CODE`, `/I2590/row`, `/I2590/total_count`)
is the portal's, identical on every sibling service; the row shape is the
documented field list (`openApiInfo.do?…&svc_no=I2590`, 7 fields), and
every one of the 7 is on every row.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "122"
down_revision: str | Sequence[str] | None = "121"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-common-standard-type"
)

PAGE_ROOT = "/I2590/row"
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
                "code": "search-common-standard-type",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                "connect_timeout_ms": 5000,
                # The portal's deep windows are slow (C006 tail 10.4s, C002
                # 28.6s); the same margin until this feed's tail is measured.
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
