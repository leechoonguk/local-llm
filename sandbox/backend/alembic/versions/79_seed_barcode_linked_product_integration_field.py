"""seed barcode linked product integration fields

Revision ID: 79
Revises: 78
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "79"
down_revision: str | Sequence[str] | None = "78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/barcode-linked-product")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-safety-korea/barcode-linked-product/{kind}")


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


# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
#
# The key is reused from the provider seeded at revision 64: one credential per portal,
# referenced by FK, so rotating it stays a single row.
#
# Filters are PATH_QUERY: they travel as a trailing path segment (변수명=값) after
# the window. Measured: sending them as a real query string is accepted and silently
# ignored.
#
# range_start/range_end are the RANGE paging family: CALLER, required, no default.

REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'C005', 'STRING', True,
     '서비스명 — 바코드연계제품정보', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('changed_from', 'CHNG_DT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '변경일자(YYYYMMDD) — 변경일자 기준 자료를 출력한다. 정수입력 : 20170101', False, 5),
    ('product_report_number', 'PRDLST_REPORT_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목제조보고번호 — 품목제조보고번호를 입력한다', False, 6),
    ('barcode', 'BAR_CD', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '바코드번호 — 바코드번호를 입력한다', False, 7),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# The provider answers HTTP 200 for every outcome and states the real one here.
# Measured: INFO-000 정상처리되었습니다 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다
ENVELOPE_ROWS = [
    ('result_code', '/C005/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상처리되었습니다 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/C005/RESULT/MSG', None, None,
     '메세지설명 — provider 가 보내는 사람이 읽는 사유', 1),
    ('total_count', '/C005/total_count', None, None,
     '조건에 해당하는 전체 건수 — 창과 무관하게 필터가 맞춘 건수다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# The 10 columns the service documents, one row each, relative to an element of
# /C005/row. Keys come from the documented 항목 설명, not from the wire name.
# All columns are optional: the provider leaves some empty for sparse records.
RESPONSE_ROWS = [
    ('product_report_no', '/PRDLST_REPORT_NO', '품목제조보고번호', False, 0),
    ('license_date', '/PRMS_DT', '허가일자', False, 1),
    ('revocation_date', '/END_DT', '폐지일자', False, 2),
    ('product_name', '/PRDLST_NM', '품목명', False, 3),
    ('shelf_life', '/POG_DAYCNT', '유통/소비기한', False, 4),
    ('product_type', '/PRDLST_DCNM', '품목유형명', False, 5),
    ('business_name', '/BSSH_NM', '업소명', False, 6),
    ('industry', '/INDUTY_NM', '업종명', False, 7),
    ('location', '/SITE_ADDR', '소재지', False, 8),
    ('closure_date', '/CLSBIZ_DT', '폐업일자', False, 9),
]


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
    op.bulk_insert(_field_table(), _rows())


def downgrade() -> None:
    field = _field_table()
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))
