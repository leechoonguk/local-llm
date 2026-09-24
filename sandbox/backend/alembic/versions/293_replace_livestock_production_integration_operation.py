"""replace livestock production integration operation with its file door

축산물 생산실적 (I1420) is the feed the paged walk never finished. The ledger
holds 29,345 rows of 2016 alone; the file holds 3,397,141 records over
2016-2025 - 99.1 % of the feed was never read, not because the portal withheld
it but because 3,398 windows do not fit a night against a daily ceiling of
about 500 calls a key.

Measured 2026-09-20 against the file:

    GET /api/{service_key}/I1420/file   200 application/gzip, 43,808,433 bytes,
                                        3,397,141 records of the same 9 columns
    every column                        100 % filled
    EVL_YR                              2016-2025, ten years in one answer
    line count vs record count          3,399,817 lines against 3,397,141
                                        records - 2,676 records carry a newline
                                        inside their quotes, which is why the
                                        reader cuts by RFC 4180 and not by line

`segment_key` and `segment_values` go to NULL: the year was how a paged walk
reached one year at a time, and a file answers all ten at once.

Replacing this row cascades `integration_field` away (FK ON DELETE CASCADE),
so revision 294 re-seeds the fields for the file.

Revision ID: 293
Revises: 292
Create Date: 2026-09-20 23:34:00.000000

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "293"
down_revision: str | Sequence[str] | None = "292"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-livestock-production"
)

PATH_TEMPLATE = "/api/{service_key}/{service_id}/file"


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
        column("segment_key", sa.String()),
        column("segment_values", sa.JSON(none_as_null=True)),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def _row() -> dict[str, object]:
    return {
        "id": OPERATION_ID,
        "provider_id": PROVIDER_ID,
        "code": "search-livestock-production",
        "method": "GET",
        "path_template": PATH_TEMPLATE,
        "request_media_type": None,
        "response_format": "CSV",
        "response_root": None,
        # Rows per chunk the stream hands the ledger stage - the same width the
        # paged walk staged, so a step of either walk reads as 1,000 rows.
        "page_size": 1000,
        "connect_timeout_ms": 5000,
        "read_timeout_ms": 60000,
        # A busy key (INFO-500, HTTP 429) clears in about 40 s; the daily ten
        # (INFO-330) it cannot, and three retries do not pretend otherwise.
        "max_retries": 3,
        "retry_base_ms": 15000,
        "retry_max_ms": 60000,
        "idempotent": True,
        "request_schema": None,
        # Nothing arrives in an envelope: a file's refusal is its HTTP status.
        "quota_codes": {},
        "segment_key": None,
        "segment_values": None,
        "enabled": True,
        "created_by": "migration",
        "updated_by": "migration",
    }


def upgrade() -> None:
    """The feed's file door replaces its paged row."""
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
    op.bulk_insert(operation, [_row()])


def downgrade() -> None:
    """Drop the row; the earlier tree re-seeds the paged one."""
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
