"""seed business integration field - the columns of the I2500 file

REQUEST is the key and the service, nothing else: the file door takes no
window and no filter. No ENVELOPE row: the body *is* the rows and a refusal is
an HTTP status. Every RESPONSE row is one CSV column under the API's own name,
read through a one-segment pointer (`/LCNS_NO`).

Measured over the whole file, 2026-09-23 (1,548,814 rows) - fill rate and width
beside each column below. The columns the ledger declines (`UNSTORED_KEYS` in
its schema) are still seeded here: the contract is what the portal answers,
and a column it answers empty is a fact worth a row.

Revision ID: 301
Revises: 300
Create Date: 2026-09-22 22:09:08.385000

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "301"
down_revision: str | Sequence[str] | None = "300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-business")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트). 파일 문의 쿼터는 API 와 별개: 인증키·서비스당 1일 10회', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I2500', 'STRING', True,
     '서비스명 — 인허가 업소 정보. 경로가 /file 로 끝나면 전체 피드가 gzip CSV 로 온다 (30.1MB, 1,548,814행, 2026-09-23)', False, 1),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('license_no', '/LCNS_NO', '인허가번호 — 11자리; 1,548,814행에 1,548,742개 (72쌍이 행정구역 개편으로 중복, 2026-09-23 파일 실측)', True, 0),
    ('industry_name', '/INDUTY_CD_NM', '업종 — 52개 값, 17자까지 (식품제조가공업 32,090 · 수입식품등 수입판매업 50,395 · 건강기능식품전문제조업 486 …)', False, 1),
    ('business_name', '/BSSH_NM', '업소명 — 56자까지', False, 2),
    ('president_name', '/PRSDNT_NM', '대표자명 — 파일 전체에서 빈 값 (0%), 개인정보로 비워 나온다', False, 3),
    ('telephone', '/TELNO', '전화번호 — 파일 전체에서 빈 값 (0%)', False, 4),
    ('permit_date', '/PRMS_DT', '허가일자 — YYYYMMDD, 1882년부터', False, 5),
    ('district', '/ADDR', '소재지 — 시·군·구까지만, 401개 값, 15자까지', False, 6),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-business/" + kind)


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
    """Seed the file door's fields."""
    op.bulk_insert(_field_table(), _rows())


def downgrade() -> None:
    """Drop this operation's fields."""
    field = _field_table()
    op.get_bind().execute(field.delete().where(field.c.operation_id == OPERATION_ID))
