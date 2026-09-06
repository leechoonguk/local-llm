"""seed food item report raw material integration operation

Revision ID: 106
Revises: 105

식품(첨가물)품목제조보고(원재료) - service C002 on 식품안전나라, confirmed by the
portal page `openApiInfo.do?svc_no=C002` whose title is that name (2026-09-06).
Same portal, same key pool, same RANGE window as I1250 (`search-food-item-report`);
only the service id and the columns differ.

Measured 2026-09-06 with the project probe (`make probe-external-api`):

    window 1/3            INFO-000  total 1071963  rows 3
    window 4/6            INFO-000  same total     rows 3, first record differs
    window 1/10           INFO-000  rows 10
    window inverted       ERROR-334 (no rows)
    /PRDLST_NM=김치       INFO-000  total 25405        <- filters as a path segment
    ?PRDLST_NM=김치       INFO-000  total 1071963      <- ignored as a query string
    /CHNG_DT=20260801     ERROR-303 최대 7일까지 증분 데이터만
    /CHNG_DT=20991231     INFO-200 해당하는 데이터가 없습니다
    /CHNG_DT=2026-08-01   ERROR-302 날짜조건은 YYYYMMDD 8자리
    tail 1071960/1071970  INFO-000  rows 4 (positions up to the total)
    1071964/1071973       INFO-200  rows 0 (one past the total: an empty page)

`total_count` equals I1250's to the record (1,071,963): one raw-material row per
item report, keyed by the same PRDLST_REPORT_NO. The verdict lives at
/C002/RESULT/CODE and the page at /C002/row, so the RESPONSE rows are
element-relative and the wrapper gets ENVELOPE rows of its own. The quota codes
are the portal's and were seeded per operation at revision 105; this row
carries the same two.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision: str = "106"
down_revision: str | Sequence[str] | None = "105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-item-report-raw-material"
)

PAGE_ROOT = "/C002/row"
PATH_TEMPLATE = "/api/{service_key}/{service_id}/{data_type}/{range_start}/{range_end}"
QUOTA_CODES = {"INFO-320": 3600, "INFO-500": 60}


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
                "code": "search-food-item-report-raw-material",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                "connect_timeout_ms": 5000,
                # Deep windows of the sibling feed measured 10-14s (p50 10.2s,
                # max 28.6s at offset 1.03M); 15s timed one of 210 calls out.
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
