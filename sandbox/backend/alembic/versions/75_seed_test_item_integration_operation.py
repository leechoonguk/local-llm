"""seed test item integration operation

Revision ID: 75
Revises: 74
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "75"
down_revision: str | Sequence[str] | None = "74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-test-item")

# 시험항목 정보 (service I2530) — a fifth operation on the portal seeded at revision 64,
# so the provider and its path-carried key are reused rather than duplicated.
#
# Measured on the wire (19:01 KST, after the provider's own 09–19 window closed, which
# answers ERROR-503 for every service including the sample key):
#
#   window 1..3         INFO-000  total_count 3393  3 rows
#   window 1..10        INFO-000  total_count 3393  10 rows   — the window resizes
#   window 9..2         ERROR-334 종료위치보다 시작위치가 더 큽니다
#   LAST_UPDT_DTM=20200318 as a path segment  INFO-000  total_count 116   — it filters
#   the same filter as a query string         INFO-000  total_count 3393  — ignored
#   LAST_UPDT_DTM=2020-03-  ERROR-302 날짜조건은 YYYYMMDD 8자리 단일값
#
# The wrapper is `{"I2530": {...}}` with `total_count` at the wrapper level, the verdict
# under `/I2530/RESULT`, and the row array under `/I2530/row`.
PAGE_ROOT = "/I2530/row"
PATH_TEMPLATE = "/api/{service_key}/{service_id}/{data_type}/{range_start}/{range_end}"


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
                "code": "search-test-item",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                "connect_timeout_ms": 5000,
                "read_timeout_ms": 15000,
                "max_retries": 2,
                "retry_base_ms": 200,
                "retry_max_ms": 1000,
                "idempotent": True,
                "request_schema": None,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
