"""seed product classification integration field

Revision ID: 69
Revises: 68
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "69"
down_revision: str | Sequence[str] | None = "68"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/product-classification")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
#
# The key is reused from the provider seeded at revision 64: one credential per portal,
# referenced by FK, so rotating it stays a single row.
#
# `last_updated_from` is a **bound**, not the record's value: it selects rows changed on
# or after that date, while the response's `last_updated_at` is a timestamp. Sharing one
# key would claim they are the same thing.
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I2510', 'STRING', True,
     '서비스명 — 식품 품목분류', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('last_updated_from', 'LAST_UPDT_DTM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '최종수정일(YYYYMMDD) — 그 날짜 이후 자료를 출력한다 (형식이 틀리면 ERROR-601)', False, 5),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# The wrapper carries the verdict for every outcome, all of them HTTP 200. Measured:
# a malformed date answers ERROR-601 ("SQL 문장 오류") where the documentation promises
# ERROR-302, which is exactly why the contract lists the codes that mean success rather
# than the codes that mean failure.
ENVELOPE_ROWS = [
    ('result_code', '/I2510/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"], 'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/I2510/RESULT/MSG', None, None, '메세지설명 — provider 가 보내는 사람이 읽는 사유', 1),
    ('total_count', '/I2510/total_count', None, None, '조건에 해당하는 전체 건수 — 창과 무관하게 필터가 맞춘 건수다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# The 19 columns the service documents, one row each, relative to an element of
# /I2510/row. `product_code` is the required one: it is the identity of a
# classification row, and every other column is empty on some level of the tree.
RESPONSE_ROWS = [
    ('level', '/LV', '레벨', False, 0),
    ('product_code', '/PRDLST_CD', '품목코드', True, 1),
    ('korean_name', '/KOR_NM', '한글명', False, 2),
    ('english_name', '/ENG_NM', '영문명', False, 3),
    ('definition', '/DFN', '정의', False, 4),
    ('valid_begin_date', '/VALD_BEGN_DT', '유효개시일자', False, 5),
    ('valid_end_date', '/VALD_END_DT', '유효종료일자', False, 6),
    ('parent_product_code', '/HRNK_PRDLST_CD', '상위품목코드', False, 7),
    ('root_product_code', '/HTRK_PRDLST_CD', '최상위품목코드', False, 8),
    ('mixture_product_yn', '/MXTR_PRDLST_YN', '조합품목여부', False, 9),
    ('attribute_seq', '/ATTRB_SEQ', '속성일련번호', False, 10),
    ('attribute_korean_name', '/PIAM_KOR_NM', '속성한글명', False, 11),
    ('product_yn', '/PRDLST_YN', '품목여부', False, 12),
    ('update_reason', '/UPDT_PRVNS', '수정사유', False, 13),
    ('use_yn', '/USE_YN', '사용여부', False, 14),
    ('remark', '/RM', '비고', False, 15),
    ('food_group_yn', '/FDGRP_YN', '식품군여부', False, 16),
    ('last_updated_at', '/LAST_UPDT_DTM', '최종수정일', False, 17),
    ('child_favorite_food_yn', '/CHD_SMBL_FD_YN', '어린이기호식품 여부', False, 18),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fast-api-standard/mfds-food-safety-korea/product-classification/{kind}")


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
