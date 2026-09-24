"""seed food recall integration field

Revision ID: 231
Revises: 230

Columns as the portal documents them (`openApiInfo.do?…&svc_no=I0490`, read
2026-09-14) crossed against the whole feed (376 rows, one window, same day):

    PRDTNM                  제품명                     376/376 filled, 61 자 최대
    RTRVLPRVNS              회수사유                   376/376, 71
    BSSHNM                  제조업체명                 376/376, 29
    ADDR                    업체주소                   373/376, 15 (시·군·구까지)
    TELNO                   전화번호                   0/376 — 전 피드 공백
    BRCDNO                  바코드번호                 222/376, 43 (여러 개를 이어 붙인다)
    FRMLCUNIT               포장단위                   339/376, 40
    MNFDT                   제조일자                   376/376, 64 — 자유 텍스트
                            ("데이터없음", "(포장일자) 2026.4.2", "20260819")
    RTRVLPLANDOC_RTRVLMTHD  회수방법                   340/376, 96
    DISTBTMLMT              유통/소비기한              334/376, 166
    PRDLST_TYPE             식품분류                   337/376, 14
    IMG_FILE_PATH           제품사진 URL               374/376, 542
    PRDLST_CD               품목코드                   376/376, 14
    CRET_DTM                등록일                     376/376, 26 (마이크로초까지)
    RTRVLDSUSE_SEQ          회수·판매중지 일련번호     376/376, 10 — 자연키
    PRDLST_REPORT_NO        품목제조보고번호           192/376, 12~15
    RTRVL_GRDCD_NM          회수등급                   368/376, 4 ("3등급")
    PRDLST_CD_NM            품목유형(품목코드명)       376/376, 42
    LCNS_NO                 업체인허가번호             297/376, 11

19 documented, 19 measured. `RTRVLDSUSE_SEQ` is the only required RESPONSE row:
it is the record's identity and never empty, while `PRDLST_REPORT_NO` is absent
on half the feed.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "231"
down_revision: str | Sequence[str] | None = "230"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-recall")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I0490', 'STRING', True,
     '서비스명 — 회수·판매중지', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('item_report_no', 'PRDLST_REPORT_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목제조보고번호 — 경로 세그먼트로 보내야 거른다(2026-09-14 실측: 경로 1건, 쿼리스트링 376건)', False, 5),
    ('created_on', 'CRET_DTM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '등록일자(YYYYMMDD) — 그 날 등록된 건', False, 6),
    ('changed_from', 'CHNG_DT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '변경일자(YYYYMMDD) — 이후 자료. 호출일 기준 7일까지만(더 오래되면 ERROR-303), 8자리가 아니면 ERROR-302 (2026-09-14 실측)', False, 7),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# HTTP 200 for every outcome; the verdict is here, as on every service of this portal.
ENVELOPE_ROWS = [
    ('result_code', '/I0490/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/I0490/RESULT/MSG', None, None,
     '메세지설명 — provider 가 보내는 사람이 읽는 사유', 1),
    ('total_count', '/I0490/total_count', None, None,
     '조건에 해당하는 전체 건수 — 창을 어디까지 옮길 수 있는지 알려준다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('recall_disuse_seq', '/RTRVLDSUSE_SEQ', '회수·판매중지 일련번호 — 이 피드의 자연키', True, 0),
    ('item_report_no', '/PRDLST_REPORT_NO', '품목제조보고번호 — 376건 중 192건에만 있다', False, 1),
    ('license_no', '/LCNS_NO', '업체인허가번호', False, 2),
    ('product_name', '/PRDTNM', '제품명', False, 3),
    ('business_name', '/BSSHNM', '제조업체명', False, 4),
    ('address', '/ADDR', '업체주소 — 시·군·구까지', False, 5),
    ('telephone', '/TELNO', '전화번호 — 전 피드가 공백(2026-09-14 실측)', False, 6),
    ('barcode_no', '/BRCDNO', '바코드번호 — 여러 개를 이어 붙인 문자열', False, 7),
    ('packaging_unit', '/FRMLCUNIT', '포장단위', False, 8),
    ('manufactured_text', '/MNFDT', '제조일자 — 자유 텍스트("데이터없음", "(포장일자) 2026.4.2")', False, 9),
    ('recall_reason', '/RTRVLPRVNS', '회수사유', False, 10),
    ('recall_method', '/RTRVLPLANDOC_RTRVLMTHD', '회수방법', False, 11),
    ('recall_grade', '/RTRVL_GRDCD_NM', '회수등급', False, 12),
    ('shelf_life_text', '/DISTBTMLMT', '유통/소비기한', False, 13),
    ('product_type_group', '/PRDLST_TYPE', '식품분류', False, 14),
    ('product_code', '/PRDLST_CD', '품목코드 — food_product_classification.product_code', False, 15),
    ('product_type_name', '/PRDLST_CD_NM', '품목유형(품목코드명)', False, 16),
    ('image_url', '/IMG_FILE_PATH', '제품사진 URL', False, 17),
    ('registered_at', '/CRET_DTM', '등록일 — 이 사건의 날짜', False, 18),
]


def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "fast-api-standard/mfds-food-safety-korea/search-food-recall/" + kind,
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
