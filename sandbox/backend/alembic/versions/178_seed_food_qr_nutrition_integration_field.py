"""seed food qr nutrition integration field

Revision ID: 178
Revises: 177

Columns as the portal documents them (the inline Swagger of
`data.go.kr/data/15143798/openapi.do`, read 2026-09-12), with the whole-feed
measurement beside each one (25,663 records, 52 windows of 500).

Five columns of the wire are not in that Swagger — the `DRSSN_*` group, which
is the 건강기능식품 1일 섭취량 (513 rows carry it, `1.000 캡슐 / 130.000 mg`).
The seed follows the wire.

The panel arrives already split, and this is the whole point of the feed: the
기준량 is `NTRTN_INDCT_CD` (총 내용량당 | 단위 내용량당 | 100g당 | 100mL당) with
its own amount and unit, the 함량 is `CTA` with `IGRD_UCD`, and the 1일
기준치 비율 is `NTRTN_RT`. The retired HACCP feed answered all of that as one
printed string (revision 173).

No caller filter is seeded: every documented filter is accepted and answers the
unfiltered `totalCount` (revision 177).
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "178"
down_revision: str | Sequence[str] | None = "177"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-nutrition")
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
    ('label_no', '/ELB_MNG_NO', 'E라벨관리번호 — 표시사항 피드의 행과 같은 번호, 2,725개', True, 0),
    ('item_report_serial', '/IMRPT_SN', '품목제조보고일련번호 — 포털 내부 일련번호', False, 1),
    ('item_report_no', '/IMRPT_NO', '품목제조보고번호 — 전 행 채움, food_item_report 로 이어지는 키', False, 2),
    ('nutrition_label_serial', '/NTRTN_INDCT_SN', '영양표시일련번호 — 한 라벨의 패널, 2,773개', False, 3),
    ('nutrition_detail_serial', '/NTRTN_IDTL_SN', '영양표시상세일련번호 — 패널 안의 한 줄, label_no 와 짝이면 유일하다', True, 4),
    ('barcode_no', '/BRCD_NO', '바코드번호', False, 5),
    ('product_name', '/PRDCT_NM', '제품명', False, 6),
    ('business_name', '/BUES_NM', '업소명', False, 7),
    ('version_no', '/VER_NO', '버전번호', False, 8),
    ('valid_from', '/VLD_BGNG_YMD', '유효시작일자 — YYYYMMDD', False, 9),
    ('valid_to', '/VLD_END_YMD', '유효종료일자 — YYYYMMDD', False, 10),
    ('basis_name', '/NTRTN_INDCT_CD', '영양표시코드명 — 기준량: 총 내용량당 | 단위 내용량당 | 100g당 | 100mL당', False, 11),
    ('total_content_amount', '/NTRTN_INDCT_TCT', '영양표시총내용량 — 숫자 (`420.000`)', False, 12),
    ('total_content_unit', '/NTRTN_INDCT_TCD', '영양표시총내용량단위명 — g | mL 등', False, 13),
    ('unit_content_amount', '/NTRTN_ICUT_CTV', '영양표시단위내용량 — 1회 제공량 등의 수치', False, 14),
    ('unit_content_unit', '/NTRTN_ICUT_CVUCD', '영양표시단위내용량단위명', False, 15),
    ('remark_text', '/NTRTN_IDRM_CN', '영양표시비고 — `1일 영양성분 기준치에 대한 비율(%)은 2,000kcal 기준…`', False, 16),
    ('format_name', '/NTRTN_IDTM_CD', '서식명 — 기본형 | 병행표기 | 세로형 | 텍스트형 등 9종', False, 17),
    ('label_group_name', '/INDCT_GROUP_NM', '표시그룹명 — 한 라벨이 여러 패널을 가질 때의 묶음 이름', False, 18),
    ('unit_content_label_name', '/UCVI_NM', '단위내용량표시명 — 3,097행만 채운다', False, 19),
    ('unit_content_label_amount_name', '/UCVI_CTA_CD', '단위내용량표시함량코드명', False, 20),
    ('total_piece_label_name', '/TPCI_NM', '총조각수표시명 — 2,960행', False, 21),
    ('nutrient_kind_name', '/NTRTN_IGRD_SE_CD', '영양성분구분명 — 필수영양성분 | 선택영양성분 | 기타영양성분 | 원재료', False, 22),
    ('nutrient_name', '/NIRWMT_NM', '영양성분명 — 84종 (열량, 나트륨, 탄수화물 …)', False, 23),
    ('nutrient_sequence', '/NIRWMT_SEQ', '영양성분순서 — 패널에 인쇄된 차례', False, 24),
    ('amount', '/CTA', '함량 — 그 성분의 값 (`215.000`), 25,585행 채움', False, 25),
    ('amount_unit', '/IGRD_UCD', '성분단위코드명 — kcal | g | mg | μg RAE | mg NE 등 9종', False, 26),
    ('amount_unit_etc', '/IGRD_UNIT_ETCD', '성분단위기타코드명 — 587행', False, 27),
    ('daily_value_pct', '/NTRTN_RT', '영양비율 — 1일 영양성분 기준치에 대한 비율(%), 18,891행 (열량에는 없다)', False, 28),
    ('additional_item_division_yn', '/ADD_IDAT_SE_YN', '추가표시항목구분여부 — Y | N', False, 29),
    ('additional_item_division_name', '/ADD_IDAT_SE_NM', '추가표시항목구분명 — 전 행 비어 있다 (2026-09-12)', False, 30),
    ('additional_item_1_name', '/ORD1_ADD_IDAT_NM', '1차추가표시항목명 — 11행', False, 31),
    ('additional_item_2_name', '/ORD2_ADD_IDAT_NM', '2차추가표시항목명 — 11행', False, 32),
    ('additional_item_3_name', '/ORD3_ADD_IDAT_NM', '3차추가표시항목명 — 전 행 비어 있다', False, 33),
    ('additional_item_4_name', '/ORD4_ADD_IDAT_NM', '4차추가표시항목명 — 전 행 비어 있다', False, 34),
    ('additional_item_5_name', '/ORD5_ADD_IDAT_NM', '5차추가표시항목명 — 전 행 비어 있다', False, 35),
    ('additional_item_1_amount', '/ORD1_ADD_IDAT_CTA', '1차추가표시항목함량 — 993행', False, 36),
    ('additional_item_2_amount', '/ORD2_ADD_IDAT_CTA', '2차추가표시항목함량 — 23행', False, 37),
    ('additional_item_3_amount', '/ORD3_ADD_IDAT_CTA', '3차추가표시항목함량 — 23행', False, 38),
    ('additional_item_4_amount', '/ORD4_ADD_IDAT_CTA', '4차추가표시항목함량 — 23행', False, 39),
    ('additional_item_5_amount', '/ORD5_ADD_IDAT_CTA', '5차추가표시항목함량 — 23행', False, 40),
    ('additional_item_1_ratio', '/ORD1_ADD_IDAT_RT', '1차추가표시항목비율 — 832행', False, 41),
    ('additional_item_2_ratio', '/ORD2_ADD_IDAT_RT', '2차추가표시항목비율 — 2행', False, 42),
    ('additional_item_3_ratio', '/ORD3_ADD_IDAT_RT', '3차추가표시항목비율 — 전 행 비어 있다', False, 43),
    ('additional_item_4_ratio', '/ORD4_ADD_IDAT_RT', '4차추가표시항목비율 — 전 행 비어 있다', False, 44),
    ('additional_item_5_ratio', '/ORD5_ADD_IDAT_RT', '5차추가표시항목비율 — 전 행 비어 있다', False, 45),
    ('additional_item_1_unit_etc', '/ORD1_IGRD_UNIT_ETCD', '1차성분단위기타코드 — 159행', False, 46),
    ('additional_item_2_unit_etc', '/ORD2_IGRD_UNIT_ETCD', '2차성분단위기타코드 — 120행', False, 47),
    ('additional_item_3_unit_etc', '/ORD3_IGRD_UNIT_ETCD', '3차성분단위기타코드 — 120행', False, 48),
    ('additional_item_4_unit_etc', '/ORD4_IGRD_UNIT_ETCD', '4차성분단위기타코드 — 120행', False, 49),
    ('additional_item_5_unit_etc', '/ORD5_IGRD_UNIT_ETCD', '5차성분단위기타코드 — 120행', False, 50),
    ('intake_basis_name', '/DRSSN_AOI_SE_CD', '1일 섭취량 구분 — 건강기능식품만 채운다 (513행), Swagger 에 없다', False, 51),
    ('intake_amount', '/DRSSN_AOI', '1일 섭취량 — 수치 (`1.000`), 497행', False, 52),
    ('intake_amount_unit', '/DRSSN_AOI_UCD', '1일 섭취량 단위 — 캡슐 등', False, 53),
    ('intake_weight', '/DRSSN_WGT', '1일 섭취중량 — 수치 (`130.000`), 497행', False, 54),
    ('intake_weight_unit', '/DRSSN_WGT_UCD', '1일 섭취중량 단위 — mg 등', False, 55),
    ('source_updated_at', '/LAST_MDFCN_DT', '최종수정일시 — YYYY-MM-DD HH:MM:SS', False, 56),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, "fast-api-standard/data-go-kr/search-food-qr-nutrition/" + kind)


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
