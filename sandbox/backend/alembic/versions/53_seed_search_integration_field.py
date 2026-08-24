"""seed mfds integration fields

Revision ID: 53
Revises: 52
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "53"
down_revision: str | Sequence[str] | None = "52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/provider")
OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")

# The provider returns 190+ columns per food record, so the operation runs in
# PASSTHROUGH mode: one response row asserts the record really is a food record
# and the canonical payload is the node at response_root, verbatim.
# (key, wire_path, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'serviceKey', 'SECRET', None, 'STRING', True,
     '인증키 (URL Encode) — 공공데이터포털에서 발급 받은 인증키', True, 0),
    ('page_no', 'pageNo', 'LITERAL', 1, 'INTEGER', False,
     '페이지 번호 (예: 1)', False, 1),
    ('num_of_rows', 'numOfRows', 'LITERAL', 100, 'INTEGER', False,
     '한 페이지 결과수 (예: 3)', False, 2),
    ('type', 'type', 'LITERAL', 'json', 'STRING', False,
     '응답데이터 형식(xml/json) default : xml', False, 3),
    ('food_name', 'FOOD_NM_KR', 'CALLER', None, 'STRING', False,
     '식품명 (예: 국밥_돼지머리)', False, 4),
    ('research_ymd', 'RESEARCH_YMD', 'CALLER', None, 'STRING', False,
     '데이터생성일자 (예: 2017-12-31)', False, 5),
    ('maker_nm', 'MAKER_NM', 'CALLER', None, 'STRING', False,
     '업체명', False, 6),
    ('food_cat1_nm', 'FOOD_CAT1_NM', 'CALLER', None, 'STRING', False,
     '식품대분류명 (예: 밥류)', False, 7),
    ('item_report_no', 'ITEM_REPORT_NO', 'CALLER', None, 'STRING', False,
     '품목제조보고번호 (예: 19760342001155)', False, 8),
    ('update_date', 'UPDATE_DATE', 'CALLER', None, 'STRING', False,
     '데이터수정일자 (예: 2025-01-23)', False, 9),
    ('db_class_nm', 'DB_CLASS_NM', 'CALLER', None, 'STRING', False,
     '품목대표/상용제품 (예: 품목대표)', False, 10),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-nutrition/{kind}")


def upgrade() -> None:
    field = table(
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
    rows = [
        {
            "id": _id(f"field:REQUEST:{key}"),
            "operation_id": OPERATION_ID,
            "direction": "REQUEST",
            "location": "QUERY",
            "key": key,
            "wire_path": wire_path,
            "value_source": value_source,
            "value": value,
            "secret_id": _id("secret:service-key") if value_source == "SECRET" else None,
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
        for key, wire_path, value_source, value, value_type, required, description, sensitive, ordinal in REQUEST_ROWS
    ]
    rows.append(
        {
            "id": _id("field:RESPONSE:food_nm_kr"),
            "operation_id": OPERATION_ID,
            "direction": "RESPONSE",
            "location": "BODY",
            "key": "food_nm_kr",
            "wire_path": "/body/items/0/FOOD_NM_KR",
            "value_source": None,
            "value": None,
            "secret_id": None,
            "value_type": "STRING",
            "format": None,
            "required": True,
            "description": "식품명 — 응답이 식품 레코드임을 확인하는 필수 필드",
            "sensitive": False,
            "ordinal": 0,
            "enabled": True,
            "match_mode": None,
            "expected_values": None,
            "created_by": "migration",
            "updated_by": "migration",
        }
    )
    op.bulk_insert(field, rows)


def downgrade() -> None:
    field = table("integration_field", column("operation_id", sa.Uuid()))
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))
