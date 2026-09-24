"""retire barcode item info integration field

Revision ID: 118
Revises: 117

The I2570 feed is a snapshot, not a feed. Measured 2026-09-06 with the project
probe: every one of its 53,242 rows carries `LAST_UPDT_DTM` 2015-01-22, the
portal answers INFO-200 to any `CHNG_DT` after that day, and its data.go.kr
twin (`15057694`, 식품바코드정보) was suspended in 2018. Eleven years of
products are missing, and a ledger that can never refresh is one row less
honest every day. The registry's live barcode source is 푸드QR, whose portal
refuses our key (data.go.kr code 30) - kept as a note, not as a seed.

The operation goes in three revisions, one table each (the migration rule):
its fields here, its row at 119, the ledger table at 120. The fields go first
because `integration_field.operation_id` cascades from the operation row -
deleting the row first would erase these silently and leave the downgrade
nothing to restore them under.

The downgrade re-seeds revision 73's rows as it wrote them, so a database
stepped back below this revision answers exactly as it did before.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "118"
down_revision: str | Sequence[str] | None = "117"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-barcode-item-info")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# Revision 73's rows, verbatim - what the downgrade puts back.
# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I2570', 'STRING', True,
     '서비스명 — 식품바코드 품목정보코드', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('changed_date', 'CHNG_DT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '변경일자(YYYYMMDD) — 변경일자 기준 이후 자료를 출력한다. 정수입력 : 20170101', False, 5),
    ('report_no', 'PRDLST_REPORT_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목제조번호 — 품목제조번호를 입력한다', False, 6),
    ('product_name', 'PRDT_NM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '제품명 — 제품을 입력한다', False, 7),
    ('barcode_no', 'BRCD_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '바코드번호 — 바코드를 입력한다', False, 8),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
ENVELOPE_ROWS = [
    ('result_code', '/I2570/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/I2570/RESULT/MSG', None, None,
     '메세지설명 — provider가 보내는 사람이 읽는 사유', 1),
    ('total_count', '/I2570/total_count', None, None,
     '조건에 해당하는 전체 건수 — 창과 무관하게 필터가 맞춘 건수다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('report_no', '/PRDLST_REPORT_NO', '품목제조번호', False, 0),
    ('report_item_name', '/PRDLST_NM', '품목명', False, 1),
    ('product_name', '/PRDT_NM', '제품명', False, 2),
    ('company_name', '/CMPNY_NM', '업소명', False, 3),
    ('barcode_no', '/BRCD_NO', '바코드번호', False, 4),
    ('upper_product_classification_name', '/HRNK_PRDLST_NM', '상위품목분류명', False, 5),
    ('top_product_classification_name', '/HTRK_PRDLST_NM', '최상위품목분류명', False, 6),
    ('last_update_datetime', '/LAST_UPDT_DTM', '최종수정일시', False, 7),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-safety-korea/search-barcode-item-info/{kind}")


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
            "id": _id(f"field:ENVELOPE:{key}"),
            "operation_id": OPERATION_ID,
            "direction": "RESPONSE",
            "location": "ENVELOPE",
            "key": key,
            "wire_path": wire_path,
            "value_source": None,
            "value": None,
            "secret_id": None,
            "value_type": "STRING",
            "format": None,
            "required": match_mode is not None,
            "description": description,
            "sensitive": False,
            "ordinal": ordinal,
            "enabled": True,
            "match_mode": match_mode,
            "expected_values": expected_values,
            "created_by": "migration",
            "updated_by": "migration",
        }
        for key, wire_path, match_mode, expected_values, description, ordinal in ENVELOPE_ROWS
    )
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
    field = _field_table()
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))


def downgrade() -> None:
    op.bulk_insert(_field_table(), _rows())
