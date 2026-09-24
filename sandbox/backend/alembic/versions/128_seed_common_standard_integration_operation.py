"""seed common standard integration operation

Revision ID: 128
Revises: 127

공통기준규격 - service I2600 on 식품안전나라. Same portal, same key pool, same
RANGE window as I2590 (`search-common-standard-type`, revision 122, which
also records why this family is built from documentation: the services
answer `ERROR-503 09시~19시에는 서비스가 제한됩니다` from 09:00 to 19:00
KST, measured 2026-09-07).

What the feed is: the rules themselves. One row per (품목 - a
`food_product_classification` code, 시험항목 - a `food_test_item` code,
단서조항) under a 공통기준 group of I2590, carrying the rule text
(`SPEC_VAL`), how it is judged (`JDGMNT_FOM_CD` 적/부텍스트, 최대/최소값,
선택형, 미생물 n/c/m), the unit and the validity dates. The documented
sample: 가공식품 (C0100000000000) × 이물 (H30001) → "① 식품은 원료의
처리과정에서 …", judged 적/부, valid 20140101-99991231. The 개별기준규격 of
I2580 (revision 131) has the same 40 columns without the group code and name.

Two filters are documented, `LAST_UPDT_DTM` and `PRDLST_CD`. Measured
2026-09-07 evening (the C006 procedure, project probe, 20:38 KST):

    window 1/3            INFO-000  total_count 57457   rows 3   8.8 s
    window inverted 3/1   ERROR-334
    tail 57456/57467      INFO-000  rows 2   7.9 s
    a full window (1000)  10-13 s  (read_timeout_ms below keeps 2x headroom)
    one past, 57458/57459 INFO-200
    /LAST_UPDT_DTM=20260901   INFO-200 (no row this week); =20260801 ERROR-303
                          (7-day reach, as revision 122); =2026-09-01 ERROR-302
                          "날짜조건은 YYYYMMDD 8자리 단일값으로 입력하십시오"
    /PRDLST_CD=E0000000000000   INFO-000 total 5 - the exact code, not the
                          E subtree (I2580 measured the same: E0101500000000 4,
                          E0000000000000 INFO-200 where it has no row);
                          =A0000000000000 total 19
    /PRDLST_CD=E01        INFO-200 - a prefix matches nothing
    an unsupported key    INFO-000 "[안내] … 사용 가능한 요청인자: PRDLST_CD,LAST_UPDT_DTM"
    CMMN_SPEC_SEQ         57,440 distinct over 57,457 rows - 16 serials repeat,
                          one row per 시험항목; (CMMN_SPEC_SEQ, TESTITM_CD) is
                          unique and is the ledger's key (revision 130)
    MXMM_VAL / MIMM_VAL   every non-empty value a decimal here, but not on
                          I2580 (revision 131) - both stay Text
    SORC                  a 고시 name (46 wide), not a code
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "128"
down_revision: str | Sequence[str] | None = "127"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-common-standard"
)

PAGE_ROOT = "/I2600/row"
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
                "code": "search-common-standard",
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
