"""replace food production integration field with the file's

The fields of the file door (revision 295) - what changed from the paged rows,
and what did not:

* REQUEST is the key and the service, and nothing else. The file door takes no
  window and no filter: the year that addressed the paged walk is a column of
  the answer here, not a coordinate of the request.
* No ENVELOPE row. A file's success has no wrapper and its refusal is an HTTP
  status the client keeps in the call log.
* The RESPONSE rows are **the same nine**, pointers unchanged. This feed has
  `SITE_ADDR` where the other two have `GUBUN`: 식품 생산실적 publishes where
  the plant is, and states no 구분 because every row of it is 식품.

Measured over the whole file, 2026-09-20 (7,927,213 records): every column
100 % filled but PRDLST_REPORT_NO (99.9 %), EVL_YR 2016-2025, 업소 55,911,
소재지 475, 품목 922, 제품명 174자까지.

Revision ID: 296
Revises: 295
Create Date: 2026-09-20 23:56:00.000000

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "296"
down_revision: str | Sequence[str] | None = "295"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-production"
)
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트). 파일 문의 쿼터는 API 와 별개: 인증키·서비스당 1일 10회 (2026-09-19 실측)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I0300', 'STRING', True,
     '서비스명 — 식품(첨가물) 생산실적. 경로가 /file 로 끝나면 전체 피드가 gzip CSV 로 온다 (123.8MB, 7,927,213행)', False, 1),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('item_report_no', '/PRDLST_REPORT_NO', '품목제조보고번호 — 99.9% 채워진다, 20자까지', True, 0),
    ('report_year', '/EVL_YR', '보고년도 — 2016~2025, 파일 한 번에 열 해가 온다 (페이징으로는 2025년만 들어와 있었다)', True, 1),
    ('product_name', '/PRDLST_NM', '제품명 — 174자까지', False, 2),
    ('business_name', '/BSSH_NM', '업소명 — 55,911개 업소, 80자까지', False, 3),
    ('license_no', '/LCNS_NO', '인허가번호 — 52,333개', False, 4),
    ('product_type_name', '/H_ITEM_NM', '품목명 — 922개', False, 5),
    ('production_qty', '/PRDCTN_QY', '생산량(kg)', False, 6),
    ('annual_capacity_qty', '/FYER_PRDCTN_ABRT_QY', '연간생산능력(kg)', False, 7),
    ('site_address', '/SITE_ADDR', '소재지 — 시·군·구까지만, 475개 값', False, 8),
]


def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "fast-api-standard/mfds-food-safety-korea/search-food-production/" + kind,
    )


def _field_table():
    return table(
        "integration_field",
        column("id", sa.Uuid()),
        column("operation_id", sa.Uuid()),
        column("direction", sa.String()),
        column("location", sa.String()),
        column("key", sa.String()),
        column("wire_path", sa.String()),
        column("value_source", sa.String()),
        column("value", sa.JSON(none_as_null=True)),
        column("secret_id", sa.Uuid()),
        column("value_type", sa.String()),
        column("format", sa.String()),
        column("required", sa.Boolean()),
        column("description", sa.String()),
        column("sensitive", sa.Boolean()),
        column("ordinal", sa.Integer()),
        column("enabled", sa.Boolean()),
        column("match_mode", sa.String()),
        column("expected_values", sa.JSON(none_as_null=True)),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "id": _id(f"field:REQUEST:{key}"),
            "operation_id": OPERATION_ID,
            "direction": "REQUEST",
            "location": location,
            "key": key,
            "wire_path": wire_path,
            "value_source": value_source,
            "value": value,
            "secret_id": SECRET_ID if value_source == "SECRET" else None,
            "value_type": value_type,
            "format": None,
            "required": required,
            "description": description,
            "sensitive": sensitive,
            "ordinal": ordinal,
            "enabled": True,
            "match_mode": None,
            "expected_values": None,
            "created_by": "migration",
            "updated_by": "migration",
        }
        for key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal in REQUEST_ROWS
    ]
    rows.extend(
        {
            "id": _id(f"field:RESPONSE:{key}"),
            "operation_id": OPERATION_ID,
            "direction": "RESPONSE",
            "location": "BODY",
            "key": key,
            "wire_path": wire_path,
            "value_source": None,
            "value": None,
            "secret_id": None,
            "value_type": "STRING",
            "format": None,
            "required": required,
            "description": description,
            "sensitive": False,
            "ordinal": ordinal,
            "enabled": True,
            "match_mode": None,
            "expected_values": None,
            "created_by": "migration",
            "updated_by": "migration",
        }
        for key, wire_path, description, required, ordinal in RESPONSE_ROWS
    )
    return rows


def upgrade() -> None:
    """Seed the file door's fields; the operation revision cascaded the paged ones away."""
    op.bulk_insert(_field_table(), _rows())


def downgrade() -> None:
    """Drop this operation's fields."""
    field = _field_table()
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))
