"""seed import food label integration operation

Revision ID: 217
Revises: 216

수입식품 수입신고별 한글표시사항 - `IprtFoodPrdtKoreanLabelingText` on the
공공데이터포털 gateway, read with this account's own key (revision 216).

**This is the 수입식품조회 screen's records, published in bulk.** Measured
2026-09-13 by walking the whole feed (2,176 windows of 500, 66 minutes,
1,087,781 records) against the screen ledger of the night before
(1,088,673 rows): the year histograms are identical - 2022 4,704/4,704,
2023 12,187/12,187, 2024 80,914/80,914, 2025 406,201/406,201, 2026
576,342/576,357 (the API run is a day younger). So the screen's paging crawl
is retired and this operation is the source (rule://backend-ledger, "One Call
Per Record Is Not A Feed").

What it adds over the screen row: `KORLABEL`, the printed 한글표시사항 in full -
1,075,586 records (98.9%), up to 8,602 characters, carrying 원재료명 및 함량,
영양정보, 내용량, 포장재질, 보관방법 and the allergen sentence. That text is what
the detail screen was going to be crawled for, at 25 days a pass.

`IRDNT_NM` (원재료명) is seeded too but is nearly empty - 7,743 of 1,087,781
(0.7%) - so the ingredient list a reader wants is inside `KORLABEL`, and
splitting it is a derived table's question, not this seed's.

A window is 17.7 seconds at 500 rows (measured), and windows cost more the
deeper they are on this gateway (363 ms at pages 1-200 against 1,441 ms at page
1,400, at 100 rows), so the read budget is 120 seconds - a window that still
runs out is then a refusal the step log names, not a night that ends quietly.

The page ceiling is **500** (measured: 1000 and 5000 answer zero rows), but the
provider job walks every feed at its own `PAGE_SIZE` of 100 - the narrowest
ceiling of this gateway's services (B553748 refuses 101) - so this feed is
10,878 windows a night, not 2,176 (rule://backend-ledger).
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "217"
down_revision: str | Sequence[str] | None = "216"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-import-food-label")

PAGE_ROOT = "/body/items"
PATH_TEMPLATE = "/1471000/IprtFoodPrdtKoreanLabelingText/getIprtFoodPrdtKoreanLabelingText"


def _operation_table() -> sa.TableClause:
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
                "code": "search-import-food-label",
                "method": "GET",
                "path_template": PATH_TEMPLATE,
                "request_media_type": None,
                "response_format": "JSON",
                "response_root": PAGE_ROOT,
                "connect_timeout_ms": 5000,
                "read_timeout_ms": 120000,
                "max_retries": 2,
                "retry_base_ms": 500,
                "retry_max_ms": 5000,
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
