"""seed health functional item report integration field

Revision ID: 239
Revises: 238

Columns as the portal documents them (`openApiInfo.do?…&svc_no=I0030`, read
2026-09-15) crossed against the whole feed (46,086 rows, 47 windows, same day):

    PRDLST_REPORT_NO    품목제조번호         46,086/46,086, 15 자 - the natural key
    PRDLST_NM           품목명               46,086, 110
    BSSH_NM             업소명               46,086, 30
    LCNS_NO             인허가번호           46,086, 11
    PRMS_DT             허가일자             46,086, 8
    PRDLST_CDNM         유형                 45,810 (99.4%), 107
    PRDT_SHAP_CD_NM     제품형태코드명       46,083, 9 ("분말")
    DISPOS              제품형태             46,068, 477 - free text, the 성상
    NTK_MTHD            섭취방법             45,675 (99.1%), 249
    PRIMARY_FNCLTY      주된기능성           45,986 (99.8%), 1,494
    IFTKN_ATNT_MATR_CN  섭취시주의사항       44,405 (96.4%), 1,242
    CSTDY_MTHD          보관방법             3,248 (7.0%), 205
    STDR_STND           기준규격             46,082, 3,062
    POG_DAYCNT          소비기한일수         46,084, 35 ("제조일로부터 24개월까지")
    FRMLC_MTRQLT        포장재질             46,086, 792
    FRMLC_MTHD          포장방법             46,081, 479
    RAWMTRL_NM          품목유형(기능지표성분) 46,073, 262
    INDIV_RAWMTRL_NM    기능성 원재료        46,084, 1,742
    ETC_RAWMTRL_NM      기타 원재료          41,764 (90.6%), 1,313
    CAP_RAWMTRL_NM      캡슐 원재료          12,482 (27.1%), 296
    HIENG_LNTRT_DVS_NM  고열량저영양여부     46,086, 4
    PRODUCTION          생산종료여부         46,086, 3 ("아니오")
    INDUTY_CD_NM        업종                 46,086, 11
    LAST_UPDT_DTM       최종수정일자         46,086, 8
    CHILD_CRTFC_YN      어린이기호식품인증   0/46,086 - empty on the whole feed

26 documented (포장재질 listed twice), 25 arrive, none missing, none extra.
`PRDLST_REPORT_NO` is the only required RESPONSE row: it is the record's
identity and never empty.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "239"
down_revision: str | Sequence[str] | None = "238"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-health-functional-item-report")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I0030', 'STRING', True,
     '서비스명 — 건강기능식품 품목제조신고', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('item_report_no', 'PRDLST_REPORT_NO', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목제조번호 — 경로 세그먼트로 보내야 거른다(2026-09-15 실측: 쿼리스트링은 46,086건 그대로)', False, 5),
    ('product_name', 'PRDLST_NM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목명', False, 6),
    ('business_name', 'BSSH_NM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '업소명', False, 7),
    ('changed_from', 'CHNG_DT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '변경일자(YYYYMMDD) — 이후 자료. 호출일 기준 7일까지만(ERROR-303), 8자리가 아니면 ERROR-302 (2026-09-15 실측)', False, 8),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# HTTP 200 for every outcome; the verdict is here, as on every service of this portal.
ENVELOPE_ROWS = [
    ('result_code', '/I0030/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/I0030/RESULT/MSG', None, None,
     '메세지설명 — provider 가 보내는 사람이 읽는 사유', 1),
    ('total_count', '/I0030/total_count', None, None,
     '조건에 해당하는 전체 건수 — 창을 어디까지 옮길 수 있는지 알려준다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('item_report_no', '/PRDLST_REPORT_NO', '품목제조번호 — 이 등록부의 자연키', True, 0),
    ('product_name', '/PRDLST_NM', '품목명', False, 1),
    ('business_name', '/BSSH_NM', '업소명', False, 2),
    ('license_no', '/LCNS_NO', '인허가번호', False, 3),
    ('permit_date', '/PRMS_DT', '허가일자(YYYYMMDD)', False, 4),
    ('product_type_name', '/PRDLST_CDNM', '유형 — 건강기능식품의 품목유형', False, 5),
    ('product_shape', '/PRDT_SHAP_CD_NM', '제품형태코드명 — 분말, 정제 등', False, 6),
    ('product_form', '/DISPOS', '제품형태 — 성상을 적은 자유 텍스트', False, 7),
    ('intake_method', '/NTK_MTHD', '섭취방법', False, 8),
    ('primary_functionality', '/PRIMARY_FNCLTY', '주된기능성', False, 9),
    ('intake_caution', '/IFTKN_ATNT_MATR_CN', '섭취시주의사항', False, 10),
    ('storage_method', '/CSTDY_MTHD', '보관방법 — 46,086건 중 3,248건만 채운다', False, 11),
    ('standard_spec', '/STDR_STND', '기준규격', False, 12),
    ('shelf_life', '/POG_DAYCNT', '소비기한일수 — "제조일로부터 24개월까지" 같은 문장', False, 13),
    ('packaging_material', '/FRMLC_MTRQLT', '포장재질', False, 14),
    ('packaging_method', '/FRMLC_MTHD', '포장방법', False, 15),
    ('functional_indicator', '/RAWMTRL_NM', '품목유형(기능지표성분)', False, 16),
    ('functional_raw_material_names', '/INDIV_RAWMTRL_NM', '기능성 원재료 — 쉼표로 이은 목록', False, 17),
    ('other_raw_material_names', '/ETC_RAWMTRL_NM', '기타 원재료 — 쉼표로 이은 목록', False, 18),
    ('capsule_raw_material_names', '/CAP_RAWMTRL_NM', '캡슐 원재료 — 쉼표로 이은 목록', False, 19),
    ('high_calorie_low_nutrition', '/HIENG_LNTRT_DVS_NM', '고열량저영양여부', False, 20),
    ('production_ended', '/PRODUCTION', '생산종료여부 — 예/아니오', False, 21),
    ('child_favorite_certified_yn', '/CHILD_CRTFC_YN', '어린이기호식품 품질인증 여부 — 전 피드가 공백(2026-09-15 실측)', False, 22),
    ('industry_name', '/INDUTY_CD_NM', '업종', False, 23),
    ('source_updated_at', '/LAST_UPDT_DTM', '최종수정일자(YYYYMMDD)', False, 24),
]


def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "fast-api-standard/mfds-food-safety-korea/search-health-functional-item-report/" + kind,
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
