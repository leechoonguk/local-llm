"""seed food inspection failure integration operation

Revision ID: 232
Revises: 231

검사부적합(국내) - service I2620 on 식품안전나라. One row per failed test item of
a domestic inspection: the item tested, the standard it had to meet, the result
that missed it, and the institution that measured it.

Read from the portal's own page (`openApiInfo.do?…&svc_no=I2620`, 2026-09-14):
18 output columns, three optional filters (`PRDTNM`, `PRDLST_REPORT_NO`,
`CHNG_DT`). 18 documented, 18 measured, none missing, none extra.

Measured 2026-09-14 (`make probe-external-api`, whole feed in one window):

    window 1/3                INFO-000  total_count 572  rows 3
    window 4/6                INFO-000  rows 3            (the window moves)
    window 1/10               INFO-000  rows 10           (and resizes)
    window inverted 5/1       ERROR-334
    /PRDTNM=부추(L23)          total_count 1     (a path segment filters)
    ?PRDTNM=부추(L23)          total_count 572   (a query string is ignored)
    /CHNG_DT=20260101         ERROR-303 ; =20991231 INFO-200 ; malformed ERROR-302
    the natural key           not the serial alone: 572 rows carry 479 distinct
                              `RTRVLDSUSE_SEQ` - one disposal is several failed
                              items - so the ledger keys on
                              (RTRVLDSUSE_SEQ, TEST_ITMNM, STDR_STND), which is
                              570 of 572. The two it collapses are rows the
                              portal sends twice, identical in all 18 columns.
    the product key           `PRDLST_REPORT_NO` is on 84 of 572 rows (14.7 %):
                              most inspections are of 농·수·축산물 with no
                              품목제조보고
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "232"
down_revision: str | Sequence[str] | None = "231"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-inspection-failure")

PAGE_ROOT = "/I2620/row"
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
                "code": "search-food-inspection-failure",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                # The portal's cap. The whole feed fits in one window, so the
                # pass is two calls: the feed and the short page after it.
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
