"""seed food qr storage integration operation

Revision ID: 189
Revises: 188

푸드QR 보관 및 취급방법 - `1471000/FoodQrInfoService02/getFoodQrSfkpTrmtInfo02`.

What the feed is: **how the package says to keep it** - `실온보관`,
`냉장보관(0~10℃)`, `냉동보관(-18℃ 이하)`, `직사광선을 피하고…` - 2,868 rows over
2,155 라벨 (whole feed, 2026-09-13), every column filled.

It is not `food_item_report.shelf_life`, which is the 소비기한 (`제조일로부터
10개월`): a storage temperature band has no column anywhere in this database.

Measured 2026-09-13: numOfRows=500 → 00, 2,868 total; the key is
(ELB_MNG_NO, FOOD_IDIF_DTL_SN) - 2,868 distinct on 2,868 rows.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "189"
down_revision: str | Sequence[str] | None = "188"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-storage")

PAGE_ROOT = "/body/items"
PATH_TEMPLATE = "/1471000/FoodQrInfoService02/getFoodQrSfkpTrmtInfo02"


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
                "code": "search-food-qr-storage",
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
