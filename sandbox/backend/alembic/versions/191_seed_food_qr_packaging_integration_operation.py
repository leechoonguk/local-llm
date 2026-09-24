"""seed food qr packaging integration operation

Revision ID: 191
Revises: 190

푸드QR 용기 및 포장재질 - `1471000/FoodQrInfoService02/getFoodQrIndctPackInfo02`.

What the feed is: **the packaging material per part** - `(내면) 폴리프로필렌`,
`용기: 무색페트`, `뚜껑: HDPE` - 6,914 rows over 3,809 라벨 (whole feed,
2026-09-13), which is the widest label set of the 푸드QR family.

`food_item_report.packaging_material` holds the same fact for 1,004,958 reports,
but as one string per report (`면-폴리프로필렌, 스프-폴리에틸렌`). Measured on the
1,838 products both cover: only 163 (8.9 %) are the same string once whitespace
and commas are dropped, because this feed splits the parts into rows. So the two
live on different axes - the report keeps its column, the label gets these rows.

Measured 2026-09-13: the key is (ELB_MNG_NO, FOOD_IDIF_DTL_SN, IMRPT_SN) -
6,914 distinct on 6,914 rows, where the pair without the 보고일련번호 collapses to
4,715 (one part reported under two 품목제조보고 serials).
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "191"
down_revision: str | Sequence[str] | None = "190"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-packaging")

PAGE_ROOT = "/body/items"
PATH_TEMPLATE = "/1471000/FoodQrInfoService02/getFoodQrIndctPackInfo02"


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
                "code": "search-food-qr-packaging",
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
