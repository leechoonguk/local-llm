"""replace mfds integration request fields with descriptions and optional params

Revision ID: 27
Revises: 26
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "27"
down_revision: str | Sequence[str] | None = "26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/search")


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-nutrition/{kind}")


def upgrade() -> None:
    request_field_table = table(
        "integration_request_field",
        column("operation_id", sa.Uuid()),
    )
    op.get_bind().execute(
        request_field_table.delete().where(
            request_field_table.c.operation_id == OPERATION_ID
        )
    )
    request_field = table(
        "integration_request_field",
        column("id", sa.Uuid()),
        column("operation_id", sa.Uuid()),
        column("input_key", sa.String()),
        column("location", sa.String()),
        column("wire_path", sa.String()),
        column("value_source", sa.String()),
        column("source_key", sa.String()),
        column("literal_value", sa.JSON(none_as_null=True)),
        column("secret_ref", sa.String()),
        column("secret_value", sa.String()),
        column("default_value", sa.JSON(none_as_null=True)),
        column("value_type", sa.String()),
        column("format", sa.String()),
        column("required", sa.Boolean()),
        column("description", sa.String()),
        column("sensitive", sa.Boolean()),
        column("ordinal", sa.Integer()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )
    # (input_key, location, wire_path, value_source, source_key, literal_value,
    #  secret_ref, secret_value, value_type, required, description, sensitive, ordinal)
    request_rows = [
        ("service_key", "QUERY", "serviceKey", "SECRET_REF", None, None,
         "mfds-service-key",
         "725c89cee973af7c02141ae7ef8f0001f025ac0a24d9766afbb101c8b25fcb4b",
         "STRING", True, "인증키 (URL Encode) — 공공데이터포털에서 발급받은 인증키",
         True, 0),
        ("page_no", "QUERY", "pageNo", "LITERAL", None, 1, None, None,
         "INTEGER", True, "페이지 번호", False, 1),
        ("num_of_rows", "QUERY", "numOfRows", "LITERAL", None, 100, None, None,
         "INTEGER", True, "한 페이지 결과수", False, 2),
        ("type", "QUERY", "type", "LITERAL", None, "json", None, None,
         "STRING", True, "응답데이터 형식(xml/json) default: xml", False, 3),
        ("food_name", "QUERY", "FOOD_NM_KR", "CALLER", "food_name", None, None, None,
         "STRING", True, "식품명", False, 4),
        ("research_ymd", "QUERY", "RESEARCH_YMD", "CALLER", "research_ymd", None, None, None,
         "STRING", False, "데이터생성일자", False, 5),
        ("maker_nm", "QUERY", "MAKER_NM", "CALLER", "maker_nm", None, None, None,
         "STRING", False, "업체명", False, 6),
        ("food_cat1_nm", "QUERY", "FOOD_CAT1_NM", "CALLER", "food_cat1_nm", None, None, None,
         "STRING", False, "식품대분류명", False, 7),
        ("item_report_no", "QUERY", "ITEM_REPORT_NO", "CALLER", "item_report_no", None, None, None,
         "STRING", False, "품목제조보고번호", False, 8),
        ("update_date", "QUERY", "UPDATE_DATE", "CALLER", "update_date", None, None, None,
         "STRING", False, "데이터수정일자", False, 9),
        ("db_class_nm", "QUERY", "DB_CLASS_NM", "CALLER", "db_class_nm", None, None, None,
         "STRING", False, "품목대표/상용제품", False, 10),
    ]
    op.bulk_insert(
        request_field,
        [
            {
                "id": _id(f"request:{input_key}"),
                "operation_id": OPERATION_ID,
                "input_key": input_key,
                "location": location,
                "wire_path": wire_path,
                "value_source": source,
                "source_key": source_key,
                "literal_value": literal_value,
                "secret_ref": secret_ref,
                "secret_value": secret_value,
                "default_value": None,
                "value_type": value_type,
                "format": None,
                "required": required,
                "description": description,
                "sensitive": sensitive,
                "ordinal": ordinal,
                "enabled": True,
                "created_by": "migration",
                "updated_by": "migration",
            }
            for input_key, location, wire_path, source, source_key, literal_value, secret_ref, secret_value, value_type, required, description, sensitive, ordinal in request_rows
        ],
    )


def downgrade() -> None:
    request_field_table = table(
        "integration_request_field",
        column("operation_id", sa.Uuid()),
    )
    op.get_bind().execute(
        request_field_table.delete().where(
            request_field_table.c.operation_id == OPERATION_ID
        )
    )