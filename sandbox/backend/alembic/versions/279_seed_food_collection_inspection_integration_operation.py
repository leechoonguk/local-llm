"""seed food collection inspection integration operation

Revision ID: 279
Revises: 278

수거검사 결과 - service I0460 on 식품안전나라, and the largest feed this project
reads: **2,046,194 rows** spanning 수거일자 20000214~20260917 (2026-09-18). One
row per specimen collected and judged: who collected it, from which business,
which product, on what day, and the verdict.

This is the feed that answers "was this product ever found unfit", and nothing
else does. Measured against its siblings: 회수·판매중지 (I0490, 379 rows) lists
only what was recalled, and 검사부적합 (I2620, 593) only what was announced. A
부적합 that led to neither appears **here alone** - which is why a product could
be judged 부적합 on 20260825 and still have no hazard information in this
database.

Read from the portal's own page (`openApiInfo.do?…&svc_no=I0460`, 2026-09-18):
the URL shape, the required five, five optional filters and 12 output columns.
12 measured here, none missing, none extra.

Measured 2026-09-18 22:0x-23:5x KST (outside the 09-19 refusal window):

    window 1/1000             INFO-000  total_count 2046503  rows 1000
    window 1/1001             INFO-000  rows 1001          (the cap is the *span*)
    window 1/1002             ERROR-336                     (1000 is that span's max)
    window 1000000/1000999    INFO-000  rows 1000          (and it moves)
    window 2046504/2046504    INFO-200  해당하는 데이터가 없습니다
    window 2046500/2047500    INFO-000  rows 5             (the short page = the end)
    /BSSH_NM=유가유치원        total_count 8        (a path segment filters)
    /TKAWYSPCI_TYPECD=1       total_count 713107   (가공식품)
    /TKAWYSPCI_TYPECD=8       total_count 285019   (식품접객업)
    /SEARCHSTDT=20260901      total_count 10702
    /SEARCHENDDT=20260910     total_count 2043177
    /SEARCHSTDT+/SEARCHENDDT  ERROR-300 필수 값이 누락 - **in XML, on the
                              `json` path**: the pair is refused, and the refusal
                              is not even the format that was asked for.
    /PRDTNM=연돈카레           total_count 2046504  (accepted and **ignored**)
    /JDGMNT_CD_NM=부적합       total_count 2046504  (accepted and **ignored**)
    /LAST_UPDT_DTM=20260918   total_count 408 ; =20260911 total_count 4538
    /LAST_UPDT_DTM=20260910   ERROR-303            (the horizon is exactly 7 days)
    /I0460/csv|xls|xlsx       ERROR-301 파일타입 값이 누락 혹은 유효하지 않습니다
                              (only xml and json are `data_type`; the file door
                              is a path of its own, `/I0460/file`)

**The price of a whole pass.** INFO-320 states it in words: "증분 파라미터를
사용하지 않으면 1시간당 100회까지만 호출할 수 있습니다". Measured sustainable on
this pool: 138 calls/hour/key (1,078 calls, 3 keys, 2.58 h, 1 refusal per key).
2,047 windows over three keys is therefore about five hours, and this feed gets a
night of its own. `LAST_UPDT_DTM` is no escape: it opens only the last 7 days,
so it can never reproduce the 2.04 M rows a ledger must equal.

**There is a cheaper door, and it is not this one.** The portal's own INFO-000
message says so - "전체 데이터를 원하시는 경우 CSV 다운로드 기능을 이용해
주십시오" - and INFO-330 prices it separately ("파일 다운로드는 인증키당
서비스별로 1일 10회"). Measured 2026-09-18: `GET /api/{service_key}/I0460/file`
answers `application/gzip`, `I0460.csv.gz`, 62,789,425 bytes in **4 seconds**,
and it decompresses to 2,046,194 rows of the same twelve columns. A whole pass
through that door is four seconds instead of five hours. It is not seeded here
because it is a different transport - one request, gzip, CSV, no envelope and no
window - and `IntegrationClient` speaks paged JSON/XML with a checked envelope.
The whole-feed figures in these seeds were measured from that file; adopting it
as a transport is a change to `app/core/integration.py`, not to a seed row.

INFO-700 is the other half of the schedule - "오늘날짜에 생성 및 변경된 데이터는
19시 이후에 호출이 가능합니다" - the portal's 09-19 KST silence, in its own words.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "279"
down_revision: str | Sequence[str] | None = "278"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/provider")
OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-collection-inspection"
)

PAGE_ROOT = "/I0460/row"
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


def upgrade() -> None:
    operation = _operation_table()
    op.bulk_insert(
        operation,
        [
            {
                "id": OPERATION_ID,
                "provider_id": PROVIDER_ID,
                "code": "search-food-collection-inspection",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                # The portal's cap, measured: a window's *span* may be 1000, so a
                # page holds at most 1001 rows and a span of 1001 is ERROR-336.
                # 1000 keeps `range_start`/`range_end` a plain stride.
                "page_size": 1000,
                "connect_timeout_ms": 5000,
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
