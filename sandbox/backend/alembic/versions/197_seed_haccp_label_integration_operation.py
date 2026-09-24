"""seed haccp label integration operation

Revision ID: 197
Revises: 196

HACCP 제품이미지 및 포장지표기정보 - `B553748/CertImgListServiceV3` on the same
공공데이터포털 gateway, read with this provider's one `service-key`. Seeded once
at revision 160 and retired at 174 because its **영양표시 arrives as one printed
string** that no parser splits honestly; it comes back now with that column left
on the wire, for the columns beside it.

Why it comes back: **it is the only feed that gives the label axis width.**
Measured over both whole feeds (2026-09-13): this one carries 14,664 records
under 14,664 품목보고번호, of which 7,983 are rows of `food_item_report`, where
the 푸드QR family carries 4,765 labels of which 1,858 resolve. The two sets are
nearly disjoint - **56 shared 보고** - so together they reach 9,750 reports
against 1,911 today.

The 56 shared ones are not duplicates: 제품명 matches on 34, 식품유형 on 37 and
내용량 on **11** (밀키스 `250mL` here against `250ml*6` there). One 품목보고번호
covers several packages and the two portals hold different ones, so a row of this
feed is its own label, never a merge target.

What is read and what is not (whole-feed fill rates, 2026-09-13):

    prdlstReportNo  14,664 (100%)  the key
    prdlstNm        14,664 (100%)  제품명
    prdkind         14,663         식품유형
    manufacture     14,664 (100%)  제조원
    seller          14,486         판매원
    rawmtrl         14,664 (100%)  원재료 - a plain comma list, unlike 푸드QR's HTML
    capacity        14,331         용량
    allergy         14,664         but 8,484 (57.9%) read 알수없음 and 41 read 없음
    barcode         5,722 numeric  the rest are 알수없음 - C005 is the barcode feed
    nutrient        12,932         one printed panel as a sentence - **not read**
    imgurl1/2       14,664         product and label photographs - **not read**

**100 is this agency's ceiling and it is the job's**: numOfRows=101 and up answer
`resultCode 13` (2026-09-13), where the 1471000 services take 500. One provider
job has one width, so `sync_data_go_kr_ledgers` walks every feed at 100 - the
nutrition feed's 639 windows become 3,191 (rule://backend-ledger).

`quota_codes` stays empty: a spent quota here is an `OpenAPI_ServiceResponse`
wrapper (code 22/23) with no `header.resultCode`, so the ENVELOPE row fails to
resolve and the call is a 502 - what "the key is spent and there is no pool"
should look like.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "197"
down_revision: str | Sequence[str] | None = "196"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-haccp-label")

PAGE_ROOT = "/body/items"
PATH_TEMPLATE = "/B553748/CertImgListServiceV3/getCertImgListServiceV3"


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
    op.bulk_insert(
        _operation_table(),
        [
            {
                "id": OPERATION_ID,
                "provider_id": PROVIDER_ID,
                "code": "search-haccp-label",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                "connect_timeout_ms": 5000,
                "read_timeout_ms": 10000,
                "max_retries": 2,
                "retry_base_ms": 200,
                "retry_max_ms": 1000,
                "idempotent": True,
                "request_schema": None,
                "quota_codes": {},
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    operation = _operation_table()
    op.get_bind().execute(operation.delete().where(operation.c.id == OPERATION_ID))
