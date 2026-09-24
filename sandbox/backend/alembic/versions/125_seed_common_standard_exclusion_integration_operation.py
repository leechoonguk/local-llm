"""seed common standard exclusion integration operation

Revision ID: 125
Revises: 124

공통기준제외 - service I2610 on 식품안전나라. Same portal, same key pool, same
RANGE window as I2590 (`search-common-standard-type`, revision 122, which
also records why this family is built from documentation: the services
answer `ERROR-503 09시~19시에는 서비스가 제한됩니다` from 09:00 to 19:00
KST, measured 2026-09-07).

What the feed is: one row per (공통기준 group, 품목, 시험항목) that a
공통기준규격 of I2600 does **not** apply to - the exceptions to the group
rules. Read with `food_common_standard`: a (product, test item) pair the
group rule covers is exempt when this ledger names it.

Measured 2026-09-07 evening (the C006 procedure, project probe, 20:38 KST):

    window 1/3            INFO-000  total_count 21   rows 3   0.5 s
    window inverted 3/1   ERROR-334
    tail 20/31            INFO-000  rows 2   0.3 s
    one past, 22/23       INFO-200
    /LAST_UPDT_DTM=20260901   INFO-200 (no row this week); =20260801 ERROR-303
                          (7-day reach, as revision 122)
    an unsupported key    INFO-000 "[안내] … 사용 가능한 요청인자: LAST_UPDT_DTM"
    **the natural key**   the documented row has no serial; the ledger keys
                          on (CMMN_SPEC_CD, PRDLST_CD, TESTITM_CD). Whole feed:
                          21 rows, 21 distinct triples, no part ever empty -
                          the key stands. Every one of the 6 fields is on
                          every row.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "125"
down_revision: str | Sequence[str] | None = "124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-common-standard-exclusion"
)

PAGE_ROOT = "/I2610/row"
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
                "code": "search-common-standard-exclusion",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                "connect_timeout_ms": 5000,
                # The portal's deep windows are slow (C006 tail 10.4s, C002
                # 28.6s); the same margin until this feed's tail is measured.
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
