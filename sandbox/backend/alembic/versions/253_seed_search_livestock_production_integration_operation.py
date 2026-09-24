"""seed 축산물 생산실적 integration operation

Revision ID: 253
Revises: 252

축산물 생산실적 - service I1420 on 식품안전나라, the same host, key pool and RANGE
window as every sibling. One row per (품목제조보고번호, 보고년도, 품목명,
인허가번호): what a reported product produced in one year, and what it could
have produced.

Read from the portal's own page (`openApiInfo.do?…&svc_no=I1420`, 2026-09-15):
9 output rows, the standard five path inputs and optional filters, of which
`EVL_YR` is the one this repository sends - not as a filter but as the
coordinate the feed is walked by (see the field revision).

Measured 2026-09-15:

    total_count               3,397,141 rows over 2016-2025; 연도별 합 = 전체
    window 1/5000             ERROR-336  (1,000 is the cap)
    /EVL_YR=2024              filters as a path segment; as a query string it is
                              ignored and the whole count comes back
    per-window latency        grows with the offset, 14.95 ms/1k행; the last
                              window of the unfiltered feed answers in 51.2 s
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "253"
down_revision: str | Sequence[str] | None = "252"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-livestock-production")

PAGE_ROOT = "/I1420/row"
PATH_TEMPLATE = "/api/{service_key}/{service_id}/{data_type}/{range_start}/{range_end}"
QUOTA_CODES = {"INFO-320": 3600, "INFO-500": 60, "INFO-300": 3600}


def _operation_table() -> sa.TableClause:
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
    """Upgrade schema."""
    op.bulk_insert(
        _operation_table(),
        [
            {
                "id": OPERATION_ID,
                "provider_id": PROVIDER_ID,
                "code": "search-livestock-production",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                # The portal's cap; 5,000 answers ERROR-336.
                "page_size": 1000,
                "connect_timeout_ms": 5000,
                # Twice the siblings': a deep window of this service answers in
                # tens of seconds (51.2 s measured on the last window of the
                # unfiltered feed, 2026-09-15).
                "read_timeout_ms": 60000,
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
    """Downgrade schema."""
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
