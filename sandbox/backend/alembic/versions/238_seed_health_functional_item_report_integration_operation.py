"""seed health functional integration operation

Revision ID: 238
Revises: 237

건강기능식품 품목제조신고 - service I0030 on 식품안전나라, the same host, key pool
and RANGE window as every sibling. One row per reported 건강기능식품: the fourth
registry beside I1250 (국내 제조 식품), C006 (축산물) and I2790 (수입식품), and it
numbers its reports in its own space.

Read from the portal's own page (`openApiInfo.do?…&svc_no=I0030`, 2026-09-15):
26 documented rows (포장재질 is listed twice), three optional filters
(`CHNG_DT`, `BSSH_NM`, `PRDLST_NM`, `PRDLST_REPORT_NO`) and the standard five
path inputs. 25 columns arrive, which is the 26 minus the repeat.

Measured 2026-09-15 (`make probe-external-api`, then the whole feed in 47
windows):

    window 1/3                INFO-000  total_count 46,086  rows 3
    window 4/6                INFO-000  rows 3            (the window moves)
    window 1/10               INFO-000  rows 10           (and resizes)
    window inverted 5/1       ERROR-334
    /PRDLST_REPORT_NO=…       INFO-200 for a number of another registry, and
                              46,086 as a query string - the path segment is
                              the filter, the query string is ignored
    /CHNG_DT=20260101         ERROR-303 ; =20991231 INFO-200 ; malformed ERROR-302
    whole feed                46,086 rows, 47 windows, every 품목제조번호 filled
                              and 15 characters at the widest
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "238"
down_revision: str | Sequence[str] | None = "237"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-health-functional-item-report")

PAGE_ROOT = "/I0030/row"
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
                "code": "search-health-functional-item-report",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                # The portal's cap, and 47 windows of it are the whole feed.
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
