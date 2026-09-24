"""seed food qr label integration field

Revision ID: 176
Revises: 175

Columns as the portal documents them (the inline Swagger of
`data.go.kr/data/15143798/openapi.do`, read 2026-09-12), with the whole-feed
measurement beside each one (2,278 records, 5 windows of 500).

Four columns of the wire are not in that Swagger — `REFRIG_FOOD_YN`,
`INTK_MTH_CONT`, `FHF_FTNLT_INFO_CN`, `MDFCN_DT` — and two it documents
(`ISSU_TYPE_CD`, `QR_URL_ADDR`) never arrive; three more it spells differently
(`PRDCT_NM`, `DSFCT_PRDCT_YN`, `STRLZ_PRDCT_YN`). The seed follows the wire,
because a key the wire does not answer reads NULL on every record forever.

No caller filter is seeded: measured on the sibling, every documented filter is
accepted and ignored (revision 175).
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "176"
down_revision: str | Sequence[str] | None = "175"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-label")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-nutrition/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'serviceKey', 'QUERY', 'SECRET', None, 'STRING', True,
     '인증키 — 공공데이터포털에서 발급된 인증키 (이 provider 의 하나뿐인 service-key)', True, 0),
    ('page_no', 'pageNo', 'QUERY', 'CALLER', None, 'INTEGER', True,
     '페이지 번호 — 1부터', False, 1),
    ('num_of_rows', 'numOfRows', 'QUERY', 'CALLER', None, 'INTEGER', True,
     '한 페이지 결과수 — 500이 상한, 1000을 보내면 resultCode 11 (2026-09-12 실측)', False, 2),
    ('type', 'type', 'QUERY', 'LITERAL', 'json', 'STRING', False,
     '응답데이터 형식 — 생략하면 xml 로 답한다 (2026-09-12 실측)', False, 3),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# This family answers `00`/`NORMAL SERVICE.` under the 1471000 agency, where
# B553748 answered `OK`/`success` (revision 173, retired). A window past the
# last page is `00` with an empty `items` list, which the walk reads as the end
# of the feed.
ENVELOPE_ROWS = [
    ('result_code', '/header/resultCode', 'ONE_OF', ["00"],
     '결과코드 — 00 정상 / 11 요청 파라미터 오류 등 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/header/resultMsg', None, None,
     '결과메시지 — NORMAL SERVICE., 또는 거부 사유', 1),
    ('total_count', '/body/totalCount', None, None,
     '전체 결과 수 — 창을 어디까지 옮길 수 있는지 알려준다', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
#
# Every pointer is relative to one element of `/body/items`, and an element is
# the record itself — this family answers `items` as a plain array.
#
# The keys are the ones the wire answers, measured over the whole feed
# (2026-09-12); where the portal's Swagger disagrees with the wire, the wire
# wins and the difference is named beside the row.
RESPONSE_ROWS = [
    ('label_no', '/ELB_MNG_NO', 'E라벨관리번호 — 레코드의 신원, 전 2,278행이 서로 다르다 (18자리)', True, 0),
    ('food_label_serial', '/FOOD_IDIF_SN', '식품표시정보일련번호 — 2,278행 중 2,218개만 서로 달라 키가 되지 못한다', False, 1),
    ('product_name', '/PRDT_NM', '제품표시명 — Swagger 는 PRDCT_NM 이라 적지만 wire 는 PRDT_NM 이다', False, 2),
    ('barcode_no', '/BRCD_NO', '바코드번호 — 전 행이 채워져 있다 (최대 14자리)', False, 3),
    ('version_no', '/VER_NO', '버전번호 — 같은 라벨의 개정 차수', False, 4),
    ('valid_from', '/VLD_BGNG_YMD', '유효일자(시작) — YYYYMMDD', False, 5),
    ('valid_to', '/VLD_END_YMD', '유효일자(종료) — YYYYMMDD, 무기한은 99991231', False, 6),
    ('food_division_name', '/FOOD_DIVS_NM', '식품구분 — 가공식품 등 (Swagger 의 FOOD_SE_CD_NM)', False, 7),
    ('food_type_name', '/FOOD_TYPE_NM', '식품유형 — 즉석조리식품, 떡류 등 (2,214/2,278 채움)', False, 8),
    ('history_tracked_yn', '/HSTT_YN', '이력추적대상여부 — Y | N', False, 9),
    ('irradiated_yn', '/EPFD_YN', '조사처리식품여부 — Y | N', False, 10),
    ('gmo_yn', '/GTRFM_FOOD_YN', '유전자변형식품여부 — Y | N', False, 11),
    ('infant_sale_marked_yn', '/IFTD_NSLI_YN', '영유아판매표시여부 — Y | N', False, 12),
    ('high_calorie_low_nutrition_yn', '/HCL_MLN_FOOD_YN', '고열량저영양식품여부 — Y | N', False, 13),
    ('pasteurized_yn', '/DSFCT_PRDT_YN', '살균제품여부 — Y | N (Swagger 의 DSFCT_PRDCT_YN)', False, 14),
    ('sterilized_yn', '/STRLZ_PRDT_YN', '멸균제품여부 — Y | N (Swagger 의 STRLZ_PRDCT_YN)', False, 15),
    ('refrigerated_yn', '/REFRIG_FOOD_YN', '냉장식품여부 — Y | N, Swagger 에 없고 wire 에만 있다', False, 16),
    ('content_amount_text', '/CTV', '내용량 — 포장 문구 그대로 (`420g (215kcal)`), 2,217행 채움', False, 17),
    ('shelf_life_text', '/CPN_TERM_CN', '소비기한(품질유지기한) — `상부 표기일까지` 같은 문구', False, 18),
    ('intake_method_text', '/INTK_MTH_CONT', '섭취방법 — 건강기능식품만 채운다 (76행)', False, 19),
    ('functional_info_text', '/FHF_FTNLT_INFO_CN', '기능성정보 — 건강기능식품만 채운다 (59행, 최대 863자)', False, 20),
    ('source_updated_at', '/MDFCN_DT', '최종수정일 — YYYY-MM-DD, 형제 피드의 19자리 일시와 달리 날짜만 온다', False, 21),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-label/" + kind)


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
