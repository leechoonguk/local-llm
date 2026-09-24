"""seed additive manufacturing closure integration operation - the file door of I2813

식품첨가물제조업 폐업정보 (I2813), seeded straight as a file: the portal publishes every
service through `/api/{key}/{service}/file` as gzip CSV, and this feed was
never walked paged. Measured 2026-09-23:

    GET /api/{service_key}/I2813/file   200 application/gzip, 41KB, 1,707 rows
    the API's total_count today         one day ahead of the file - the file
                                        is built nightly, the API answers live
    every column                        the API's own names, UTF-8 BOM, CRLF

식품첨가물제조업의 폐업 인허가. I2500 과 겹치지 않는다 — 0/1,707.

No paging inputs, no root, no envelope (rule://backend-integration-configuration,
"A File Is a Transport"): a chunk of `page_size` rows is the walk's page, and a
refusal is an HTTP status (429 for a busy key or the day's ten downloads).

Revision ID: 306
Revises: 305
Create Date: 2026-09-22 22:09:08.386000

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "306"
down_revision: str | Sequence[str] | None = "305"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-additive-manufacturing-closure")

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
        "code": "search-food-additive-manufacturing-closure",
        "method": "GET",
        "path_template": PATH_TEMPLATE,
        "request_media_type": None,
        "response_format": "CSV",
        "response_root": None,
        # Rows per chunk the stream hands the ledger stage - the width every
        # file feed of this portal is staged at, so a step reads as 1,000 rows.
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
    """Seed the file door of I2813."""
    op.bulk_insert(_operation_table(), [_row()])


def downgrade() -> None:
    """Drop the row; its fields go with it (FK ON DELETE CASCADE)."""
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
