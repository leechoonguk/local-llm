"""seed livestock item report raw material integration operation

Revision ID: 115
Revises: 114

축산물품목제조보고(원재료) - service C006 on 식품안전나라. Same portal, same key
pool, same RANGE window as C002 (`search-food-item-report-raw-material`); the
service id, the filter set and one column differ.

Why this feed: the nutrition ledger names 축산물가공품 (`수지스 닭다리살
스테이크`, item report 202507260114) that neither I1250 nor C002 hold - the
registry numbers livestock products on a service of their own. Measured
2026-09-07 with the project probe:

    window 1/3            INFO-000  total 569588   rows 3
    window 4/6            INFO-000  same total     rows 3, other records
    window 1/10           INFO-000  rows 10
    window inverted       ERROR-334 (no rows)
    tail 569587/569600    INFO-000  rows 2, 10.4s (deep windows are slow here too)
    569589/569598         INFO-200  rows 0 (one past the total: an empty page)
    /PRDLST_REPORT_NO=…   INFO-000  total 1
    /LCNS_NO=19990030770  INFO-000  total 54
    /PRMS_DT=20250101     INFO-000  total 104556   <- on/after, as on C002
    /CHNG_DT=20260905     INFO-000  total 51
    /CHNG_DT=20260801     ERROR-303 최대 7일까지 증분 데이터만
    /CHNG_DT=2026-08-01   ERROR-302 날짜조건은 YYYYMMDD 8자리
    /PRDLST_NM=포장육      INFO-000  total 569588 - "[안내] PRDLST_NM 은(는) 이
                          서비스에서 지원하지 않는 요청인자 … 사용 가능한 요청인자:
                          PRDLST_REPORT_NO,CHNG_DT,PRMS_DT,LCNS_NO"

So C006 filters on four keys only: a name, a type or a raw material sent as a
filter is announced as ignored in the message and the whole feed answers. The
verdict lives at /C006/RESULT/CODE and the page at /C006/row. The quota codes
are the portal's, seeded per operation since revision 105.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision: str = "115"
down_revision: str | Sequence[str] | None = "114"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL,
    "fast-api-standard/mfds-food-safety-korea/search-livestock-item-report-raw-material",
)

PAGE_ROOT = "/C006/row"
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
    op.bulk_insert(
        operation,
        [
            {
                "id": OPERATION_ID,
                "provider_id": PROVIDER_ID,
                "code": "search-livestock-item-report-raw-material",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                "connect_timeout_ms": 5000,
                # The tail window answered in 10.4s; C002's deep windows
                # reached 28.6s, and 15s timed one of 210 calls out there.
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
