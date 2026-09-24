"""seed food inspection failure integration field

Revision ID: 233
Revises: 232

Columns as the portal documents them (`openApiInfo.do?…&svc_no=I2620`, read
2026-09-14) crossed against the whole feed (572 rows, one window, same day):

    PRDTNM            제품명            572/572 filled, 61 자 최대
    BSSHNM            업소명            572/572, 22 ("전*복" — 개인은 가려서 낸다)
    MNFDT             제조일자          572/572, 21 — 자유 텍스트
    DISTBTMLMT        유통/소비기한     274/572, 36
    ADDR              영업자주소        568/572, 15
    INSTT_NM          검사기관          533/572, 38
    REGSTR_TELNO      전화번호          0/572 — 전 피드 공백
    BRCDNO            바코드번호        80/572, 20
    FRMLCUNIT         포장단위          112/572, 30
    TEST_ITMNM        부적합항목        572/572, 28
    STDR_STND         기준규격          572/572, 44
    TESTANALS_RSLT    검사결과          572/572, 43
    CRET_DTM          등록일            572/572, 10 ("2026.03.11" — 점으로 끊는다)
    RTRVLDSUSE_SEQ    회수폐기일련번호  572/572, 10 — 479 개만 서로 다르다
    PRDLST_REPORT_NO  품목제조보고번호  84/572, 12~15
    LCNS_NO           업체인허가번호    137/572, 11
    REPORTR_TELNO     보고자전화번호    0/572 — 전 피드 공백
    PRDLST_CD_NM      식품유형          572/572, 12

18 documented, 18 measured. Three RESPONSE rows are required because the key is
their triple: one disposal is several failed items (3000232082 carries four
농약 on one 로즈마리), and two items of one disposal differ only by the standard
they were judged against (3000231595 살모넬라균, 내용물1/6/13).
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "233"
down_revision: str | Sequence[str] | None = "232"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-inspection-failure")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I2620', 'STRING', True,
     '서비스명 — 검사부적합(국내)', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('item_report_no', 'PRDLST_REPORT_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목제조보고번호 — 경로 세그먼트로 보내야 거른다(2026-09-14 실측: 경로 1건, 쿼리스트링 572건)', False, 5),
    ('product_name', 'PRDTNM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '제품명 — 완전일치', False, 6),
    ('changed_from', 'CHNG_DT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '변경일자(YYYYMMDD) — 이후 자료. 호출일 기준 7일까지만(ERROR-303), 8자리가 아니면 ERROR-302 (2026-09-14 실측)', False, 7),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# HTTP 200 for every outcome; the verdict is here, as on every service of this portal.
ENVELOPE_ROWS = [
    ('result_code', '/I2620/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/I2620/RESULT/MSG', None, None,
     '메세지설명 — provider 가 보내는 사람이 읽는 사유', 1),
    ('total_count', '/I2620/total_count', None, None,
     '조건에 해당하는 전체 건수 — 창을 어디까지 옮길 수 있는지 알려준다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('disposal_seq', '/RTRVLDSUSE_SEQ', '회수폐기일련번호 — 한 처분에 여러 부적합항목이 달린다', True, 0),
    ('test_item_name', '/TEST_ITMNM', '부적합항목 — 자연키의 두 번째', True, 1),
    ('standard_text', '/STDR_STND', '기준규격 — 자연키의 세 번째(같은 항목이 기준만 달리 붙는다)', True, 2),
    ('test_result_text', '/TESTANALS_RSLT', '검사결과 — 측정값 또는 검출 여부', False, 3),
    ('institution_name', '/INSTT_NM', '검사기관', False, 4),
    ('item_report_no', '/PRDLST_REPORT_NO', '품목제조보고번호 — 572건 중 84건에만 있다', False, 5),
    ('license_no', '/LCNS_NO', '업체인허가번호', False, 6),
    ('product_name', '/PRDTNM', '제품명', False, 7),
    ('business_name', '/BSSHNM', '업소명', False, 8),
    ('address', '/ADDR', '영업자주소', False, 9),
    ('barcode_no', '/BRCDNO', '바코드번호', False, 10),
    ('packaging_unit', '/FRMLCUNIT', '포장단위', False, 11),
    ('manufactured_text', '/MNFDT', '제조일자 — 자유 텍스트', False, 12),
    ('shelf_life_text', '/DISTBTMLMT', '유통/소비기한', False, 13),
    ('product_type_name', '/PRDLST_CD_NM', '식품유형', False, 14),
    ('registered_on', '/CRET_DTM', '등록일 — 이 사건의 날짜("2026.03.11")', False, 15),
    ('registrar_telephone', '/REGSTR_TELNO', '전화번호 — 전 피드가 공백(2026-09-14 실측)', False, 16),
    ('reporter_telephone', '/REPORTR_TELNO', '보고자전화번호 — 전 피드가 공백(2026-09-14 실측)', False, 17),
]


def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "fast-api-standard/mfds-food-safety-korea/search-food-inspection-failure/" + kind,
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
