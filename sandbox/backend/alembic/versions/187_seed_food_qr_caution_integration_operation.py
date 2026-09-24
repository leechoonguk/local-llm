"""seed food qr caution integration operation

Revision ID: 187
Revises: 186

푸드QR 식품표시정보 주의사항 - `1471000/FoodQrInfoService02/getFoodQrIndctAttnInfo02`,
the same host, key and window as its 표시사항 sibling (revision 175).

What the feed is: the **주의사항 문구 a package prints**, one row per sentence -
8,134 rows over 2,154 라벨 (whole feed, 2026-09-13), every column filled. It is
the only place this harness can read 교차오염 from: 1,198 of those rows say
`이 제품은 …을 사용한 제품과 같은 제조시설에서 제조하였습니다`, which the
알레르기 feed does not carry (that one lists what is *in* the product). The rest
are 부정·불량식품 신고 1399 (1,631), 교환·환불 (1,565), 개봉 후 보관 (415) and
어린이 질식 주의 (39).

`food_item_report` has no column for any of this, so nothing here is a second
copy of something we hold.

Measured 2026-09-13: numOfRows=500 → 00, 8,134 total; the key is
(ELB_MNG_NO, FOOD_IDIF_DTL_SN) - 8,134 distinct on 8,134 rows.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "187"
down_revision: str | Sequence[str] | None = "186"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-caution")

PAGE_ROOT = "/body/items"
PATH_TEMPLATE = "/1471000/FoodQrInfoService02/getFoodQrIndctAttnInfo02"


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
                "code": "search-food-qr-caution",
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
