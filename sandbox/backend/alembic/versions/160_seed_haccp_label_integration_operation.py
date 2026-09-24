"""seed haccp label integration operation

Revision ID: 160
Revises: 158

HACCP 제품이미지 및 포장지표기정보 - `B553748/CertImgListServiceV3` on the
공공데이터포털 gateway this provider already names, read with the provider's
one `service-key`: the portal re-issued it, and the key the account holds
now is approved for both agencies under this host (revision 162).

What the feed is: the **label** of a HACCP-certified product, as the
certifying body recorded it - 원재료 (one comma-joined string), 알레르기
유발물질, 영양성분 (the printed 영양표시, as text), 바코드, 용량, 제조원,
판매원 and two image URLs, under the 품목보고번호 the product reports under.
It is not a second nutrition database: `nutrient` is the package's own
printed panel, where `search-food-nutrition` carries 식약처's analysed values.

Measured 2026-09-12 (whole feed, 147 windows):

    numOfRows=100, pageNo=1     OK      14,666 total, 100 rows
    numOfRows=101 (and 500)     13      "numOfRows : LIMITED_OF_DATA_EXCEEDS_ERROR"
    pageNo=500 (past the end)   OK      items [] - the walk's own end rule
    serviceKey=WRONG            HTTP 403 SERVICE_KEY_IS_NOT_REGISTERED_ERROR (30)
    ?prdlstReportNo=201904962715  total 1     - filters
    ?prdlstNm=김부각              total 5     - filters
    ?productGb=식품               total 14666 - accepted and ignored, so no row
    returnType omitted          XML - the LITERAL row keeps JSON on the wire
    whole feed                  14,666 rows, 14,666 distinct 품목보고번호

**100 is the ceiling and it is louder than the sibling's**: the 1471000
services answer an over-wide window with an empty page (revision 58's
measurement), this one answers `resultCode 13`. Either way the job's
`PAGE_SIZE` is the measured ceiling, and here that is 100.

`quota_codes` stays empty like its sibling: this gateway reports a spent
quota as an `OpenAPI_ServiceResponse` wrapper (code 22/23), which carries no
`header.resultCode` at all - the ENVELOPE row then fails to resolve and the
call is a 502, which is what "the key is spent and there is no pool" should
look like. A quota code here would claim a rotation this provider's single
key cannot do.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "160"
down_revision: str | Sequence[str] | None = "158"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-haccp-label")

# The page, never its first record: every RESPONSE row is relative to one
# element, and an element here is `{"item": {...}}` - the gateway wraps each
# record in its own `item` node.
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
    operation = _operation_table()
    op.bulk_insert(
        operation,
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
                # A full window answered in under a second through the whole
                # measuring walk (147 windows, 2026-09-12); the sibling's
                # 10 s keeps the same order of headroom.
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
