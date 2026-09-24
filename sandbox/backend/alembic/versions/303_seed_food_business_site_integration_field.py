"""seed business site integration field - the columns of the I2560 file

REQUEST is the key and the service, nothing else: the file door takes no
window and no filter. No ENVELOPE row: the body *is* the rows and a refusal is
an HTTP status. Every RESPONSE row is one CSV column under the API's own name,
read through a one-segment pointer (`/LCNS_NO`).

Measured over the whole file, 2026-09-23 (1,545,751 rows) - fill rate and width
beside each column below. The columns the ledger declines (`UNSTORED_KEYS` in
its schema) are still seeded here: the contract is what the portal answers,
and a column it answers empty is a fact worth a row.

Revision ID: 303
Revises: 302
Create Date: 2026-09-22 22:09:08.386000

"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "303"
down_revision: str | Sequence[str] | None = "302"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATION_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-business-site")
SECRET_ID = uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/secret:service-key")

# REQUEST — (key, wire_path, location, value_source, value, value_type, required, description, sensitive, ordinal)
REQUEST_ROWS = [
    ('service_key', 'service_key', 'PATH', 'SECRET', None, 'STRING', True,
     '인증키 — OpenAPI 에서 발급된 인증키 (경로 세그먼트). 파일 문의 쿼터는 API 와 별개: 인증키·서비스당 1일 10회', True, 0),
    ('service_id', 'service_id', 'PATH', 'LITERAL', 'I2560', 'STRING', True,
     '서비스명 — 영업소재지 GIS 코드. 경로가 /file 로 끝나면 전체 피드가 gzip CSV 로 온다 (46.3MB, 1,545,751행, 2026-09-23)', False, 1),
]

# RESPONSE — (key, wire_path, description, required, ordinal)
RESPONSE_ROWS = [
    ('license_no', '/LCNS_NO', '인허가번호 — 1,545,751행에 1,545,680개 (71쌍 중복, 2026-09-23)', True, 0),
    ('business_name', '/BSSH_NM', '업소명 — 56자까지', False, 1),
    ('district', '/LOCPLC', '소재지 — 시·군·구까지, 1,051개 값, 18자까지', False, 2),
    ('is_mountain', '/SAN', '산 여부 — 95.1%, 한 글자', False, 3),
    ('lot_main_no', '/LNBR', '지번 본번 — 95.0%, 20자까지', False, 4),
    ('lot_sub_no', '/ISSNO', '지번 부번 — 72.9%', False, 5),
    ('tong', '/TONG', '통 — 0.1%', False, 6),
    ('ban', '/BAN', '반 — 0.1%', False, 7),
    ('special_address', '/SPCLADDR', '특수지주소 — 0%', False, 8),
    ('special_dong', '/SPCPPDONG', '특수지 동 — 2.8%', False, 9),
    ('special_sub_no', '/SPCPPISSNO', '특수지 부번 — 7.1%', False, 10),
    ('road_district_code', '/ROADNMSIGNGUCD', '도로명 시군구코드 — 98.8%, 5자리', False, 11),
    ('road_emd_kind', '/ROADNMADDREMDDVS', '도로명 읍면동 구분 — 0%', False, 12),
    ('road_emd_code', '/ROADNMADDREMDCD', '도로명 읍면동 코드 — 0%', False, 13),
    ('road_floor_kind', '/ROADNMADDRBDFLRDVS', '도로명 지상지하 구분 — 0%', False, 14),
    ('road_building_main_no', '/ROADNMADDRBDORIGNO', '도로명 건물 본번 — 0%', False, 15),
    ('road_building_sub_no', '/ROADNMADDRBDSUBNO', '도로명 건물 부번 — 0%', False, 16),
    ('road_special_address', '/ROADNMADDRSPCLADDR', '도로명 특수지 — 0%', False, 17),
    ('parcel_code', '/PNU_CD', '필지고유번호 — 19자리, 28.6% 채워진다', False, 18),
    ('building_no', '/BDMERGEMANAGENO', '건물관리번호 — 28자, 24.0% 채워진다; 한 부지에 인허가 여럿이면 이 값이 같다', False, 19),
    ('ufid', '/UFID_CD', 'UFID — 17자, 22.0%', False, 20),
]


def _id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, "fast-api-standard/mfds-food-safety-korea/search-food-business-site/" + kind)


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
