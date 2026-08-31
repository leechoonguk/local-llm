"""seed food safety korea integration operation

Revision ID: 70
Revises: 69
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "70"
down_revision: str | Sequence[str] | None = "69"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/food-raw-material")

# 식품 원재료 코드 (service I2520) — a third operation on the portal seeded at revision
# 64, so the provider and its path-carried key are reused rather than duplicated.
#
# Measured: the URL is `.../{startIdx}/{endIdx}/변수명=값&변수명=값2`, so filters append
# as a trailing path segment after the window. The response wrapper is `{"I2520": {...}}`
# with `total_count` at the wrapper level and the row array under `I2520/row`.

PAGE_ROOT = "/I2520/row"
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
                "code": "search-food-raw-material",
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
