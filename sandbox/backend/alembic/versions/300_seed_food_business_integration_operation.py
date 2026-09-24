"""seed business integration operation - the file door of I2500

인허가 업소 정보 (I2500), seeded straight as a file: the portal publishes every
service through `/api/{key}/{service}/file` as gzip CSV, and this feed was
never walked paged. Measured 2026-09-23:

    GET /api/{service_key}/I2500/file   200 application/gzip, 30.1MB, 1,548,814 rows
    the API's total_count today         one day ahead of the file - the file
                                        is built nightly, the API answers live
    every column                        the API's own names, UTF-8 BOM, CRLF

살아 있는 인허가 전부, 음식점 포함 — 52개 업종. 우리가 읽는 9개 업종(제조·첨가물·건기식 제조 2·축산 가공 3·식육포장·수입판매)은 94,751행이고, 파생(food_business)이 거른다. 같은 번호가 두 번 오는 행이 72쌍 있다(행정구역 개편으로 다시 적힌 같은 업소 — 인천 중구/제물포구) — 스테이지가 먼저 온 것을 남긴다.

No paging inputs, no root, no envelope (rule://backend-integration-configuration,
"A File Is a Transport"): a chunk of `page_size` rows is the walk's page, and a
refusal is an HTTP status (429 for a busy key or the day's ten downloads).

Revision ID: 300
Revises: 299
Create Date: 2026-09-22 22:08:36.551000

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "300"
down_revision: str | Sequence[str] | None = "299"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-business")

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
        "code": "search-food-business",
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
    """Seed the file door of I2500."""
    op.bulk_insert(_operation_table(), [_row()])


def downgrade() -> None:
    """Drop the row; its fields go with it (FK ON DELETE CASCADE)."""
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
