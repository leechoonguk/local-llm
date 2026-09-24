"""seed food qr label integration operation

Revision ID: 175
Revises: 174

푸드QR 식품표시정보 - `1471000/FoodQrInfoService02/getFoodQrIndctInfo02`, the
same host, the same 1471000 agency and the same one `service-key` the nutrition
feed already reads (measured 2026-09-12: this key answers, and all three
식품안전나라 keys answer HTTP 403 code 30 here).

What the feed is: the **표시사항** a package carries, one row per E라벨관리번호 -
제품표시명, 바코드번호, 식품구분·식품유형, 내용량 (`420g (215kcal)`), 소비기한
문구, and eight 여부 flags (이력추적·조사처리·유전자변형·영유아판매·고열량저영양·
살균·멸균·냉장). It is the row the label axis hangs on: revisions 177-180 add its
영양표시 and 알레르기 siblings, and the three replace the HACCP free-text feed
retired in revisions 170-174.

Measured 2026-09-12 (whole feed, 5 windows):

    numOfRows=500, pageNo=1     00      2,278 total, 500 rows
    numOfRows=1000              11      INVALID_REQUEST_PARAMETER_ERROR
    pageNo past the end         00      items [] - the walk's own end rule
    serviceKey=WRONG            HTTP 403 SERVICE_KEY_IS_NOT_REGISTERED_ERROR (30)
    type omitted                XML - the LITERAL row keeps JSON on the wire
    whole feed                  2,278 rows, 2,278 distinct ELB_MNG_NO

**500 is the ceiling and this gateway says so**: the sibling 1471000 service
answers an over-wide window with an empty page (revision 58), this family
answers `resultCode 11`. Either way `PAGE_SIZE` is 500, which is what
`sync_data_go_kr_ledgers` already sends.

**No filter is modelled, because none of them filter.** Measured on the 영양표시
sibling: `brcdNo`, `imrptNo`, `prdctNm` and `elbMngNo` are each accepted and
answered `totalCount` 25,663 - the whole set, unfiltered. A caller row for any of
them would be a filter this API does not have.

`quota_codes` stays empty for the reason its siblings carry: this gateway reports
a spent quota as an `OpenAPI_ServiceResponse` wrapper (code 22/23) with no
`header.resultCode` at all, so the ENVELOPE row fails to resolve and the call is
a 502 - which is what "the key is spent and there is no pool" should look like.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "175"
down_revision: str | Sequence[str] | None = "174"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-label")

# The page, never its first record: every RESPONSE row is relative to one
# element, and an element here is the record itself - this family answers
# `items` as a plain array (measured 2026-09-12), unlike B553748's `item` node.
PAGE_ROOT = "/body/items"
PATH_TEMPLATE = "/1471000/FoodQrInfoService02/getFoodQrIndctInfo02"


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
                "code": "search-food-qr-label",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                "connect_timeout_ms": 5000,
                # A 500-row window answered in about a second through the whole
                # measuring walk (2026-09-12); the sibling's 10 s keeps the same
                # order of headroom.
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
