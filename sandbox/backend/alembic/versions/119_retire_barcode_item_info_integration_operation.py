"""retire barcode item info integration operation

Revision ID: 119
Revises: 118

The second of three: revision 118 took the operation's fields, this one takes
its row (`search-barcode-item-info`, seeded at revision 72), revision 120
drops the ledger it fed. Why the feed goes is written on 118.

`integration_call.operation_id` is ON DELETE SET NULL, so the call log keeps
every window the job ever asked of I2570 - they just no longer name the
operation.

The downgrade re-seeds revision 72's row as revision 105 last left it (the
portal's quota codes, added to every operation of the provider there).
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "119"
down_revision: str | Sequence[str] | None = "118"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-barcode-item-info")

PAGE_ROOT = "/I2570/row"
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
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))


def downgrade() -> None:
    op.bulk_insert(
        _operation_table(),
        [
            {
                "id": OPERATION_ID,
                "provider_id": PROVIDER_ID,
                "code": "search-barcode-item-info",
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
                "quota_codes": QUOTA_CODES,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )
