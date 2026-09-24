"""replace food collection inspection integration operation with its file door

The paged operation seeded at revision 279 cannot be walked whole. Measured
2026-09-19 with the job itself: 1,576 calls over five hours, throughput 311 →
278 → 533 → 219 → 150 → 0 windows an hour as the three keys reached 498, 496
and 497 successful calls and answered `INFO-300` (유효 호출건수를 이미 초과);
the pass died at window 1,495 of 2,047, and the ledger - correctly - kept its
old rows. The daily ceiling is about 500 calls a key, the feed is 2,047
windows, and no schedule of one night fits the two.

The portal's own answer is in its INFO-000 message - "전체 데이터를 원하시는
경우 CSV 다운로드 기능을 이용해 주십시오" - and this row takes it:

    GET /api/{service_key}/I0460/file      200 application/gzip, I0460.csv.gz,
                                           62,801,312 bytes in 3-4 s;
                                           2,046,504 rows of the same 12 columns,
                                           the header in the portal's order
    the same, twice in a row               429, XML INFO-500 "현재 접속 중인
                                           인증키" - clears in about 40 s
    the eleventh of a day, one key         429, XML INFO-330 "파일 다운로드는
                                           인증키당 서비스별로 1일 10회"
    with the API key at INFO-300           200 - the file quota is its own
    /I0460/csv, /xls, /xlsx                ERROR-301: a file is a path, not a
                                           data_type
    the recorded API window 1/2            both rows found in the file, every
                                           column identical to the microsecond

So: `response_format` CSV, no root (the file is the page), no envelope (a
refusal is its status), no paging inputs (a chunk of `page_size` rows is the
walk's page), and retries wide enough to wait out a busy key: 15 s, 30 s, 60 s.
`quota_codes` is empty because nothing here arrives in an envelope.

Replacing this row cascades `integration_field` away (FK ON DELETE CASCADE),
so revision 287 re-seeds the fields for the file.

Revision ID: 286
Revises: 285
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "286"
down_revision: str | Sequence[str] | None = "285"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-collection-inspection"
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
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def _row() -> dict[str, object]:
    return {
        "id": OPERATION_ID,
        "provider_id": PROVIDER_ID,
        "code": "search-food-collection-inspection",
        "method": "GET",
        "path_template": PATH_TEMPLATE,
        "request_media_type": None,
        "response_format": "CSV",
        "response_root": None,
        # Rows per chunk the stream hands the ledger stage - the same width the
        # paged walk staged, so a step of either walk reads as 1,000 rows.
        "page_size": 1000,
        "connect_timeout_ms": 5000,
        # 62.8 MB arrives in 3-4 s from this host; a read timeout is per read
        # of the stream, not per file, so a minute is generous and not idle.
        "read_timeout_ms": 60000,
        # A busy key (INFO-500, HTTP 429) clears in about 40 s: three retries
        # at 15, 30 and 60 s wait it out; the daily ten (INFO-330) they cannot.
        "max_retries": 3,
        "retry_base_ms": 15000,
        "retry_max_ms": 60000,
        "idempotent": True,
        "request_schema": None,
        "quota_codes": {},
        "enabled": True,
        "created_by": "migration",
        "updated_by": "migration",
    }


def upgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
    op.bulk_insert(operation, [_row()])


def downgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
