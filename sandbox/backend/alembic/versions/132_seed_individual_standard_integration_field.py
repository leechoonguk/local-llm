"""seed individual standard integration field

Revision ID: 132
Revises: 131

Columns as the portal documents them (`openApiInfo.do?…&svc_no=I2580`, read
2026-09-07 - the service itself is closed 09:00-19:00 KST, see revision 122),
with a measured row instead of the documentation's samples (the page
repeats I2600's samples column for column; this is 2017001103 / C10002
세균수 of 유산균음료, read 2026-09-07 evening):

    INDV_SPEC_SEQ          개별기준규격일련번호         "2017001103"
    PRDLST_CD              품목분류코드                 "C0309060100000" (I2510)
    PRDLST_CD_NM           품목명                       "유산균음료"
    TESTITM_CD             시험항목코드                 "C10002"      (I2530)
    TESTITM_NM             시험항목명                   "세균수"
    FNPRT_ITM_NM           세부항목명                   "세균수"
    ATTRB_SEQ              단서조항일련번호             "2022000003"
    PIAM_KOR_NM            단서조항명                   "살균제품에 한한다"
    SPEC_VAL               기준규격                     "n=5, c=1, m=100, M=1000"
    SPEC_VAL_SUMUP         기준규격요약                 ""
    VALD_BEGN_DT           유효개시일                   "20180101"
    VALD_END_DT            유효종료일                   "99991231"
    SORC                   출처                         "식품공전(제2022-76호)"
    VALD_MANLI             유효자리                     ""
    JDGMNT_FOM_CD          판정형식코드                 "03"
    A079_FNPRT_CD_NM       판정형식명                   "3군법"
    MXMM_VAL               최대값                       ""
    MXMM_VAL_DVS_CD        최대값구분코드               ""
    A081_FNPRT_CD_NM       최대값구분명                 ""
    MIMM_VAL               최소값                       ""
    MIMM_VAL_DVS_CD        최소값구분코드               ""
    A080_FNPRT_CD_NM       최소값구분명                 ""
    CHOIC_FIT              선택형적합코드               ""
    A082_CF_FNPRT_CD_NM    선택형적합명                 ""
    CHOIC_IMPROPT          선택형부적합코드             ""
    A082_CI_FNPRT_CD_NM    선택형부적합명               ""
    MCRRGNSM_2N            미생물2N                     "5"
    MCRRGNSM_2C            미생물2C                     "1"
    MCRRGNSM_2M            미생물2M                     "100"
    MCRRGNSM_3M            미생물3M                     "1000"
    FNPRT_ITM_INCLS_YN     세부항목포함여부             "N"
    INJRY_YN               위해여부                     "N"
    EMPHS_PRSEC_TESTITM_YN 중점검사시험항목여부         "N"
    MONTRNG_TESTITM_YN     감시시험항목여부             "N"
    RVLV_ELSE_TESTITM_YN   공전외시험항목여부           "N"
    NTR_PRSEC_ITM_YN       자품검사시험항목여부         "N"
    UNIT_CD                단위코드                     "011"
    UNIT_NM                단위명                       "CFU/g"
    UPDT_PRVNS             수정사유                     "최초등록"
    LAST_UPDT_DTM          최종수정일시                 "2023-07-03 10:18:46.823081"

40 documented (I2600's list without the group code and name), and measured
over the whole feed (16,401 rows): every record carries all 40 keys.
`INDV_SPEC_SEQ` is NOT unique - 322 serials carry up to 17 rows, split by
시험항목, 세부항목 (2016003195 / B90516: 비스페놀A beside "") and 단서조항
(2017001103 / C10002: this 살균 clause beside a 멸균 one) - so the ledger
keys on (INDV_SPEC_SEQ, TESTITM_CD, FNPRT_ITM_NM, ATTRB_SEQ), which is
unique (revision 133). The two filters are the documented `LAST_UPDT_DTM` and
`PRDLST_CD`, PATH_QUERY as on every sibling of this portal (I2530
measured: the trailing path segment filters, a real query string is
ignored). Measured (revision 131 has the table): the date is a lower
bound reaching back 7 days (20260904 -> 7; older -> ERROR-303;
non-8-digit -> ERROR-302); the product code is an exact match
(E0101500000000 -> 4, E0000000000000 -> INFO-200, E01 -> INFO-200), not
a subtree.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "132"
down_revision: str | Sequence[str] | None = "131"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-individual-standard"
)
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I2580', 'STRING', True,
     '서비스명 — 개별기준규격', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 정수입력 (시작위치보다 작으면 ERROR-334)', False, 4),
    ('last_updated_from', 'LAST_UPDT_DTM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '최종수정일(YYYYMMDD) — 하한(이상). 호출일 기준 7일 이내만(더 오래되면 ERROR-303), 8자리가 아니면 ERROR-302 (2026-09-07 실측)', False, 5),
    ('product_code', 'PRDLST_CD', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '품목분류코드 — food_product_classification.product_code 와 정확 일치(하위 트리 아님, 접두어는 INFO-200 — 2026-09-07 실측)', False, 6),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# HTTP 200 for every outcome; the verdict is here. INFO-200 is an empty page
# on every sibling service (measured one past the total on C006), which a walk
# reads as the end of the feed.
ENVELOPE_ROWS = [
    ('result_code', '/I2580/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/I2580/RESULT/MSG', None, None,
     '메세지설명 — provider 가 보내는 사람이 읽는 사유 (지원하지 않는 필터의 [안내] 도 여기 실린다)', 1),
    ('total_count', '/I2580/total_count', None, None,
     '조건에 해당하는 전체 건수 — 창을 어디까지 옮길 수 있는지 알려준다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# `individual_standard_seq` is the required one: it is the key the ledger
# upserts on - the documented serial of the rule row.
RESPONSE_ROWS = [
    ('individual_standard_seq', '/INDV_SPEC_SEQ', '개별기준규격일련번호 — 규격 행의 일련번호', True, 0),
    ('product_code', '/PRDLST_CD', '품목분류코드 — food_product_classification.product_code', False, 1),
    ('product_name', '/PRDLST_CD_NM', '품목명', False, 2),
    ('test_item_code', '/TESTITM_CD', '시험항목코드 — food_test_item.test_item_code', False, 3),
    ('test_item_name', '/TESTITM_NM', '시험항목명', False, 4),
    ('detail_item_name', '/FNPRT_ITM_NM', '세부항목명', False, 5),
    ('clause_seq', '/ATTRB_SEQ', '단서조항일련번호', False, 6),
    ('clause_name', '/PIAM_KOR_NM', '단서조항명', False, 7),
    ('standard_value', '/SPEC_VAL', '기준규격 — 규격 본문', False, 8),
    ('standard_value_summary', '/SPEC_VAL_SUMUP', '기준규격요약', False, 9),
    ('valid_begin_date', '/VALD_BEGN_DT', '유효개시일(YYYYMMDD)', False, 10),
    ('valid_end_date', '/VALD_END_DT', '유효종료일(YYYYMMDD, 99991231 = 무기한)', False, 11),
    ('source_code', '/SORC', '출처', False, 12),
    ('valid_digits', '/VALD_MANLI', '유효자리', False, 13),
    ('judgment_format_code', '/JDGMNT_FOM_CD', '판정형식코드', False, 14),
    ('judgment_format_name', '/A079_FNPRT_CD_NM', '판정형식명 — 적/부텍스트 등', False, 15),
    ('maximum_value', '/MXMM_VAL', '최대값', False, 16),
    ('maximum_value_type_code', '/MXMM_VAL_DVS_CD', '최대값구분코드', False, 17),
    ('maximum_value_type_name', '/A081_FNPRT_CD_NM', '최대값구분명 — 미만/이하 등', False, 18),
    ('minimum_value', '/MIMM_VAL', '최소값', False, 19),
    ('minimum_value_type_code', '/MIMM_VAL_DVS_CD', '최소값구분코드', False, 20),
    ('minimum_value_type_name', '/A080_FNPRT_CD_NM', '최소값구분명', False, 21),
    ('choice_fit_code', '/CHOIC_FIT', '선택형적합코드', False, 22),
    ('choice_fit_name', '/A082_CF_FNPRT_CD_NM', '선택형적합명 — 음성 등', False, 23),
    ('choice_unfit_code', '/CHOIC_IMPROPT', '선택형부적합코드', False, 24),
    ('choice_unfit_name', '/A082_CI_FNPRT_CD_NM', '선택형부적합명 — 양성 등', False, 25),
    ('microbe_2n', '/MCRRGNSM_2N', '미생물2N — n/c/m 규격의 n', False, 26),
    ('microbe_2c', '/MCRRGNSM_2C', '미생물2C', False, 27),
    ('microbe_2m', '/MCRRGNSM_2M', '미생물2M', False, 28),
    ('microbe_3m', '/MCRRGNSM_3M', '미생물3M — 3단계 규격의 M', False, 29),
    ('detail_item_included_yn', '/FNPRT_ITM_INCLS_YN', '세부항목포함여부', False, 30),
    ('hazard_yn', '/INJRY_YN', '위해여부', False, 31),
    ('priority_inspection_yn', '/EMPHS_PRSEC_TESTITM_YN', '중점검사시험항목여부', False, 32),
    ('monitoring_yn', '/MONTRNG_TESTITM_YN', '감시시험항목여부', False, 33),
    ('outside_codex_yn', '/RVLV_ELSE_TESTITM_YN', '공전외시험항목여부', False, 34),
    ('self_inspection_yn', '/NTR_PRSEC_ITM_YN', '자품검사시험항목여부', False, 35),
    ('unit_code', '/UNIT_CD', '단위코드', False, 36),
    ('unit_name', '/UNIT_NM', '단위명 — mg/kg 등', False, 37),
    ('update_reason', '/UPDT_PRVNS', '수정사유', False, 38),
    ('last_updated_at', '/LAST_UPDT_DTM', '최종수정일시', False, 39),
]

def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "fast-api-standard/mfds-food-safety-korea/search-individual-standard/" + kind,
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
