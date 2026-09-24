"""seed individual standard integration operation

Revision ID: 131
Revises: 130

개별기준규격 - service I2580 on 식품안전나라. Same portal, same key pool, same
RANGE window as I2590 (`search-common-standard-type`, revision 122, which
also records why this family is built from documentation: the services
answer `ERROR-503 09시~19시에는 서비스가 제한됩니다` from 09:00 to 19:00
KST, measured 2026-09-07).

What the feed is: the rules a 품목 carries on its own, as opposed to the
공통기준 rules of I2600 (revision 128) that a group of 품목 shares. One row
per (품목 - a `food_product_classification` code, 시험항목 - a
`food_test_item` code, 단서조항), keyed by the serial `INDV_SPEC_SEQ`, with
the same 40 rule columns as I2600 minus the group code and name
(`CMMN_SPEC_CD`/`SPEC_NM`). Judging a 품목 means reading both ledgers: its
own rows here, plus the group rows of I2600 that `food_common_standard_
exclusion` (I2610, revision 125) does not strike out.

Two filters are documented, `LAST_UPDT_DTM` and `PRDLST_CD`. Measured
2026-09-07 evening (the C006 procedure, project probe, 19:36-20:38 KST):

    window 1/3            INFO-000  total_count 16401   rows 3   2.5 s
    window inverted 5/1   ERROR-334
    window 1/1001         INFO-000 - a 1001-row window is accepted here
    tail 16400/16411      INFO-000  rows 2   2.3 s
    a full window (1000)  5.4 s  (read_timeout_ms below)
    one past, 16402/16403 INFO-200
    /LAST_UPDT_DTM=20260904   INFO-000 total 7 = the rows stamped on/after
                          2026-09-04 (a lower bound); =20260801 ERROR-303
                          "호출일자 기준 최대 7일까지 증분 데이터만 호출할 수
                          있습니다" (7-day reach); a future date INFO-200;
                          =2026-09-04 ERROR-302 (8 digits only)
    /PRDLST_CD=E0101500000000   INFO-000 total 4 = the rows with exactly that
                          code; =E0000000000000 INFO-200 (no row carries the
                          root itself). Exact match, not a subtree; =E01 INFO-200 (a prefix matches nothing)
    an unsupported key    INFO-000 "[안내] … 사용 가능한 요청인자: PRDLST_CD,LAST_UPDT_DTM"
    INDV_SPEC_SEQ         14,138 distinct over 16,401 rows - 322 serials repeat
                          (up to 17 rows), across 시험항목, 세부항목 and 단서조항;
                          (INDV_SPEC_SEQ, TESTITM_CD, FNPRT_ITM_NM, ATTRB_SEQ) is
                          unique and is the ledger's key (revision 133) - the
                          last two are empty on 14,135 / 14,226 rows
    MXMM_VAL / MIMM_VAL   14 of 972 distinct values are ratios (`15:1`) or
                          powers (`1.0*10^10`) - Text stays
    SORC                  a 고시 name (`식품공전(제2022-76호)`, 55 wide), not a code
    PRDLST_CD prefixes    C 3,582 · D 6,900 · E 4,624 · F 399 · H 856 · G 36 · B 4 -
                          the 식품공전 subsets (I0950 D, I0960 E, I0940 F) are
                          inside this feed, which is why none of them is read
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "131"
down_revision: str | Sequence[str] | None = "130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-individual-standard"
)

PAGE_ROOT = "/I2580/row"
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
                "code": "search-individual-standard",
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
