"""seed food collection inspection integration field

Revision ID: 280
Revises: 279

The wire fields of 수거검사 결과 — service I0460 on 식품안전나라. Five required
path parts, the five optional filters its 요청인자 table lists, the envelope this
portal answers every outcome with, and the 12 response columns of its 출력항목
table.

Measured 2026-09-18 (the seed operation's docstring carries the whole table).
Three facts shape these rows:

* **Two of the five documented filters do not filter.** `PRDTNM` and
  `JDGMNT_CD_NM` are accepted and ignored - a request for 연돈카레 answers all
  2,046,504 rows - so neither is seeded. A field that cannot narrow the feed is
  not a filter, and a caller who is handed one reads a whole feed believing it
  asked a question.
* **`SEARCHSTDT` and `SEARCHENDDT` may not be sent together**: the pair answers
  `ERROR-300` in XML on the `json` path. Each is seeded; a caller that sends
  both gets the portal's refusal, and the envelope check turns it into one.
* **No column, and no combination of columns, identifies a row.** 수거증번호
  repeats 651,739 times over the whole feed (1,394,455 distinct of 2,046,194),
  and so does every composite of the twelve. Even the whole record repeats:
  1,037 rows of the portal's own single-file snapshot are identical in all
  twelve values, so it is the publisher repeating itself, not a walk seeing a
  row twice. This operation therefore has no natural key to declare, and its
  ledger keys on a digest of the whole record.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "280"
down_revision: str | Sequence[str] | None = "279"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(
    NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-collection-inspection"
)
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트)', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I0460', 'STRING', True,
     '서비스명 — 수거검사 결과', False, 1),
    ('data_type', 'data_type', 'PATH', 'LITERAL', 'json', 'STRING', True,
     '요청파일 타입 — xml : xml파일 , json : json파일', False, 2),
    ('range_start', 'range_start', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청시작위치 — 정수입력 (1부터)', False, 3),
    ('range_end', 'range_end', 'PATH', 'CALLER', None, 'INTEGER', True,
     '요청종료위치 — 시작위치와의 간격은 1000까지, 1001이면 ERROR-336 (2026-09-18 실측)', False, 4),
    ('business_name', 'BSSH_NM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '업소명 — 부분일치로 거른다(2026-09-18 실측: 유가유치원 → 8건)', False, 5),
    ('specimen_type_code', 'TKAWYSPCI_TYPECD', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '검체구분 — 0수산물 1가공식품 2식품첨가물 3건강기능식품 4농산물 5축산물 6기구용기 7위생용품 8식품접객업 9기타 (2026-09-18 실측: 1 → 713,107건, 8 → 285,019건)', False, 6),
    ('collected_from', 'SEARCHSTDT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '수거시작일자(YYYYMMDD) — SEARCHENDDT 와 함께 보내면 ERROR-300 을 XML 로 답한다(2026-09-18 실측)', False, 7),
    ('collected_until', 'SEARCHENDDT', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '수거종료일자(YYYYMMDD) — SEARCHSTDT 와 함께 보내면 ERROR-300 (2026-09-18 실측)', False, 8),
    ('updated_since', 'LAST_UPDT_DTM', 'PATH_QUERY', 'CALLER', None, 'STRING', False,
     '최종수정일자(YYYYMMDD) — 증분 파라미터. 최근 7일까지만 열리고 8일 전은 ERROR-303 (2026-09-18 실측)', False, 9),
]

# ENVELOPE — (key, wire_path, match_mode, expected_values, description, ordinal)
#
# HTTP 200 for every outcome; the verdict is here, as on every service of this
# portal — an invalid key answered INFO-100 with HTTP 200 (2026-09-18 실측).
ENVELOPE_ROWS = [
    ('result_code', '/I0460/RESULT/CODE', 'ONE_OF', ["INFO-000", "INFO-200"],
     'INFO-000 정상 처리 / INFO-200 해당하는 데이터가 없습니다 — 그 밖의 코드는 호출을 거부한다', 0),
    ('result_message', '/I0460/RESULT/MSG', None, None,
     '메세지설명 — provider 가 보내는 사람이 읽는 사유', 1),
    ('total_count', '/I0460/total_count', None, None,
     '조건에 해당하는 전체 건수 — 2,046,503(2026-09-18 실측, 하루에 수백 건씩 늘어난다)', 2),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('collection_no', '/TKAWYPRNO', '수거증번호 — 유일하지 않다. 전 피드에서 651,739건이 중복(2026-09-18 실측)', False, 0),
    ('product_name', '/PRDTNM', '제품명 — 122자까지 측정, 공백은 231건뿐', False, 1),
    ('business_name', '/BSSH_NM', '업소명 — 농수산물·축산물 수거는 업소가 없어 40.8%가 공백', False, 2),
    ('address', '/SITE_ADDR', '소재지 — 시·군·구까지만 공개, 42.0%가 공백', False, 3),
    ('industry_name', '/PRCSCITYPOINT_INDUTYCD_NM', '업종 — 44.5%가 공백', False, 4),
    ('specimen_type', '/TKAWYSPCI_TYPECD_NM', '검체구분 — 가공식품 713,015 / 농산물 318,957 / 식품접객업 284,977 / 축산물(축산물가공품) 282,788 … 요청 코드에 없는 환경검체 395건도 온다', False, 5),
    ('collected_on', '/TKAWYDTM', '수거일자(YYYYMMDD) — 20000214~20260917, 공백 없음', False, 6),
    ('judgment', '/JDGMNT_CD_NM', '판정결과 — 적합 68.3% / 공백 21.1%(미공표) / 상기와같음 5.4% / 검토중 4.7% / 부적합 0.43%(8,861건)', False, 7),
    ('institution_name', '/EXC_INSTT_NM', '수행기관명 — 36자까지 측정', False, 8),
    ('item_report_no', '/PRDLST_REPORT_NO', '품목제조보고번호 — 19자까지, 32.6%만 채워진다. 품목보고(food_item_report)와 잇는 유일한 키', False, 9),
    ('plan_title', '/PLAN_TITL', '수거계획명 — 어떤 계획으로 수거했는지, 4.9%가 공백', False, 10),
    ('source_updated_text', '/LAST_UPDT_DTM', '최종수정일시 — "2026-09-18 16:25:59.676351" 꼴', False, 11),
]


def _id(kind: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        "fast-api-standard/mfds-food-safety-korea/search-food-collection-inspection/" + kind,
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
