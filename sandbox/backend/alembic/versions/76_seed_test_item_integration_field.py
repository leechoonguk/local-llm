"""seed test item integration field

Revision ID: 76
Revises: 75
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "76"
down_revision: str | Sequence[str] | None = "75"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-test-item")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
#
# The key is reused from the provider seeded at revision 64: one credential per portal,
# referenced by FK, so rotating it stays a single row.
#
# `last_updated_from` is PATH_QUERY, and that is measured rather than read from the
# spec: `LAST_UPDT_DTM=20200318` as a trailing path segment answers total_count 116,
# and the same filter as a real query string answers 3393 — the unfiltered total, so
# the provider accepts and ignores it.
#
# range_start/range_end are the RANGE paging family: CALLER, required, no default.
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I2530', 'STRING', True,
     '서비스명 — 시험항목 정보', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('last_updated_from', 'LAST_UPDT_DTM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '최종수정일(YYYYMMDD) — 측정: 20200318 → 전체 3393건 중 116건, 8자리가 아니면 ERROR-302', False, 5),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# The provider answers HTTP 200 for every outcome and states the real one here.
# Measured: INFO-000 정상처리 / INFO-200 해당하는 데이터가 없습니다 / ERROR-334 역전된 창 /
# ERROR-302 날짜 형식 오류 — I1250은 같은 상황에서 ERROR-601이므로 코드는 operation마다 다르다.
ENVELOPE_ROWS = [
    ('result_code', '/I2530/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/I2530/RESULT/MSG', None, None,
     '메세지설명 — provider가 보내는 사람이 읽는 사유', 1),
    ('total_count', '/I2530/total_count', None, None,
     '조건에 해당하는 전체 건수 — 창과 무관하게 필터가 맞춘 건수다 (필터 없이 3393)', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# The 15 columns the service documents, one row each, relative to an element of
# /I2530/row. Keys come from the documented 항목 설명, not from the wire name:
# `TESTITM_LCLAS_CD` names nothing a caller can read, 시험항목대분류시퀀스 does.
#
# Only the code is required — it is what makes the record the record. Measured on the
# first page: ABRV, NCKNM and REMN_MTTR_DFN come back as empty strings, so a required
# row on any of them would turn a normal answer into a 502.
RESPONSE_ROWS = [
    ('test_item_code', '/TESTITM_CD', '시험항목코드', True, 0),
    ('korean_name', '/KOR_NM', '한글명', False, 1),
    ('english_name', '/ENG_NM', '영문명', False, 2),
    ('abbreviation', '/ABRV', '약어', False, 3),
    ('alias', '/NCKNM', '이명', False, 4),
    ('test_item_name', '/TESTITM_NM', '시험항목명', False, 5),
    ('major_class_sequence', '/TESTITM_LCLAS_CD', '시험항목대분류시퀀스', False, 6),
    ('major_class_code', '/L_ATTRB_CD', '시험항목대분류코드', False, 7),
    ('major_class_korean_name', '/L_KOR_NM', '대분류한글명', False, 8),
    ('middle_class_sequence', '/TESTITM_MLSFC_CD', '시험항목중분류시퀀스', False, 9),
    ('middle_class_code', '/M_ATTRB_CD', '시험항목중분류코드', False, 10),
    ('middle_class_korean_name', '/M_KOR_NM', '중분류한글명', False, 11),
    ('residue_definition', '/REMN_MTTR_DFN', '잔류물질정의', False, 12),
    ('in_use', '/USE_YN', '사용여부', False, 13),
    ('last_updated_at', '/LAST_UPDT_DTM', '최종수정일시', False, 14),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-safety-korea/search-test-item/{kind}")


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
    op.bulk_insert(_field_table(), _rows())


def downgrade() -> None:
    field = _field_table()
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))
