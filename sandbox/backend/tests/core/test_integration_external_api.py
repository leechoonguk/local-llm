"""External API contract tests for seeded integration operations.

Each seeded external API integration gets a contract test here that verifies
request rendering (path, query, headers, body) and response normalization
against a mock transport. A new seeded operation must add a corresponding
contract test in this file — enforced by `check-backend-integration-configuration`.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import re
from pathlib import Path
from typing import cast

import httpx2
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import IntegrationError
from app.core.integration import IntegrationClient
from app.models.base import Base
from app.models.integration.field import IntegrationField
from app.models.integration.operation import IntegrationOperation
from app.models.integration.provider import Integration
from app.models.integration.secret import IntegrationSecret
from app.schemas.integration.field import IntegrationFieldCreateRequest
from app.schemas.integration.operation import IntegrationOperationCreateRequest
from app.schemas.integration.provider import IntegrationCreateRequest
from app.schemas.integration.secret import IntegrationSecretCreateRequest
from app.services.integration.provider import IntegrationProviderService


def operation(**overrides) -> IntegrationOperation:
    """Build a minimal operation whose defaults keep tests fast.

    The millisecond timeouts and tiny backoff exist so a retry path can be
    exercised without making the suite wait.
    """
    provider = Integration(
        code="test",
        display_name="Test",
        base_url="https://example.com",
        min_interval_ms=0,
        enabled=True,
    )
    values = {
        "code": "lookup",
        "method": "GET",
        "path_template": "/lookup",
        "request_media_type": None,
        "response_format": "JSON",
        "response_root": None,
        "connect_timeout_ms": 10,
        "read_timeout_ms": 50,
        "max_retries": 2,
        "retry_base_ms": 1,
        "retry_max_ms": 2,
        "idempotent": True,
        "request_schema": None,
        "enabled": True,
        "fields": [],
    }
    values.update(overrides)
    return IntegrationOperation(provider=provider, **values)


def client(handler, **overrides) -> IntegrationClient:
    """Wrap an operation in a client whose transport is the given handler.

    The handler is where a contract test asserts what left the process.
    """
    return IntegrationClient(
        operation=operation(**overrides),
        client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_execute_rejects_mfds_error_response() -> None:
    """An error body carries no page, and a page that carries nothing maps nothing.

    The provider answers HTTP 200 with `resultCode ERROR-300` and an empty body, so
    the failure has to be named by the contract: the root resolves to nothing, which
    for a declared page is an empty answer — and an empty answer to a call that asked
    for a window is what the caller must be able to tell apart from data.
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={"header": {"resultCode": "ERROR-300", "resultMsg": "MISSING KEY"}, "body": {}},
        )

    configured = client(
        handler,
        response_root="/body/items",
        fields=[
            IntegrationField(
                direction="RESPONSE",
                location="BODY",
                key="food_name",
                wire_path="/FOOD_NM_KR",
                value_type="STRING",
                required=True,
            )
        ],
    )
    try:
        assert (await configured.execute({})).canonical_payload == []
    finally:
        await configured.aclose()


@pytest.mark.asyncio
async def test_execute_rejects_a_body_that_is_not_a_page() -> None:
    """A provider that answers with a record where the contract declares a page.

    This is the one shape mapping cannot absorb: the rows are written relative to an
    element, so a single object at the root would silently map its own keys and hand
    back one record for a paged call.
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"body": {"items": {"FOOD_NM_KR": "김치"}}})

    configured = client(
        handler,
        response_root="/body/items",
        fields=[
            IntegrationField(
                direction="RESPONSE",
                location="BODY",
                key="food_name",
                wire_path="/FOOD_NM_KR",
                value_type="STRING",
                required=True,
            )
        ],
    )
    try:
        with pytest.raises(IntegrationError, match="not a page"):
            await configured.execute({})
    finally:
        await configured.aclose()


ITEM_REPORT_RECORD = {
    "LCNS_NO": "19550509001",
    "BSSH_NM": "매일식품주식회사",
    "PRDLST_REPORT_NO": "1955050900169",
    "PRMS_DT": "20030825",
    "PRDLST_NM": "진미순간장",
    "PRDLST_DCNM": "혼합간장",
    "PRODUCTION": "아니오",
    "HIENG_LNTRT_DVS_NM": "해당없음",
    "CHILD_CRTFC_YN": "",
    "POG_DAYCNT": "제조일로부터 2년",
    "LAST_UPDT_DTM": "20260701",
    "INDUTY_CD_NM": "식품제조가공업",
    "QLITY_MNTNC_TMLMT_DAYCNT": "",
    "USAGE": "조리시 적절하게 첨가하여 이용한다",
    "PRPOS": "",
    "DISPOS": "진한 적갈색의 액상으로, 간장 특유의 향미가 있음",
    "FRMLC_MTRQLT": "",
    "ETQTY_XPORT_PRDLST_YN": "O",
}


def _item_report_client(handler: object, **updates: object) -> IntegrationClient:
    """A client shaped like the seeded I1250 operation: path key, window, filters."""
    service_key = IntegrationSecret(name="service-key", value="issued-key", enabled=True)
    fields = [
        IntegrationField(
            direction="REQUEST",
            location="PATH",
            key="service_key",
            wire_path="service_key",
            value_source="SECRET",
            secret=service_key,
            value_type="STRING",
            required=True,
            sensitive=True,
        ),
        IntegrationField(
            direction="REQUEST",
            location="PATH",
            key="service_id",
            wire_path="service_id",
            value_source="LITERAL",
            value="I1250",
            value_type="STRING",
            required=True,
            ordinal=1,
        ),
        IntegrationField(
            direction="REQUEST",
            location="PATH",
            key="data_type",
            wire_path="data_type",
            value_source="LITERAL",
            value="json",
            value_type="STRING",
            required=True,
            ordinal=2,
        ),
        IntegrationField(
            direction="REQUEST",
            location="PATH",
            key="range_start",
            wire_path="range_start",
            value_source="CALLER",
            value_type="INTEGER",
            required=True,
            ordinal=1,
        ),
        IntegrationField(
            direction="REQUEST",
            location="PATH",
            key="range_end",
            wire_path="range_end",
            value_source="CALLER",
            value_type="INTEGER",
            required=True,
            ordinal=2,
        ),
        IntegrationField(
            direction="REQUEST",
            location="PATH_QUERY",
            key="product_name",
            wire_path="PRDLST_NM",
            value_source="CALLER",
            value_type="STRING",
            required=False,
            ordinal=3,
        ),
        IntegrationField(
            direction="RESPONSE",
            location="ENVELOPE",
            key="result_code",
            wire_path="/I1250/RESULT/CODE",
            value_type="STRING",
            required=True,
            match_mode="ONE_OF",
            expected_values=["INFO-000", "INFO-200"],
        ),
        IntegrationField(
            direction="RESPONSE",
            location="ENVELOPE",
            key="total_count",
            wire_path="/I1250/total_count",
            value_type="STRING",
            required=False,
            ordinal=1,
        ),
        IntegrationField(
            direction="RESPONSE",
            location="BODY",
            key="product_name",
            wire_path="/PRDLST_NM",
            value_type="STRING",
            required=True,
        ),
        IntegrationField(
            direction="RESPONSE",
            location="BODY",
            key="business_name",
            wire_path="/BSSH_NM",
            value_type="STRING",
            required=False,
            ordinal=1,
        ),
    ]
    return client(
        handler,
        path_template="/api/{service_key}/{service_id}/{data_type}/{range_start}/{range_end}",
        response_root="/I1250/row",
        fields=fields,
        **updates,
    )


CLASSIFICATION_RECORD = {
    "LV": "1",
    "PRDLST_CD": "A0000000000000",
    "KOR_NM": "식물성",
    "ENG_NM": "",
    "DFN": "",
    "VALD_BEGN_DT": "20140101",
    "VALD_END_DT": "99991231",
    "HRNK_PRDLST_CD": "",
    "HTRK_PRDLST_CD": "A0000000000000",
    "MXTR_PRDLST_YN": "N",
    "ATTRB_SEQ": "",
    "PIAM_KOR_NM": "",
    "PRDLST_YN": "N",
    "UPDT_PRVNS": "최초등록",
    "USE_YN": "Y",
    "RM": "",
    "FDGRP_YN": "N",
    "LAST_UPDT_DTM": "2021-06-18 11:15:36.860505",
    "CHD_SMBL_FD_YN": "N",
}


# The first row the live service returns for `RPRSNT_RAWMTRL_NM=김치` (measured), all
# 17 documented columns as the provider sends them - empty strings included.
RAW_MATERIAL_RECORD = {
    "RAWMTRL_CD": "A5000122007714",
    "RAWMTRL_LCLAS_NM": "식품원료(A코드)",
    "RAWMTRL_MLSFC_NM": "미생물",
    "RPRSNT_RAWMTRL_NM": "김치유산균배양액",
    "RAWMTRL_NCKNM": "",
    "ENG_NM": "",
    "SCNM": "",
    "REGN_CD": "00",
    "REGN_CD_NM": "-",
    "PRCSS_PROCS_CD": "77",
    "PRCSS_PROCS_CD_NM": "배양",
    "RAWMTRL_STATS_CD": "14",
    "RAWMTRL_STATS_CD_NM": "액",
    "VALD_BGN_DT": "20150603",
    "VALD_END_DT": "20150605",
    "USE_YN": "N",
    "LAST_UPDT_DTM": "2016-01-11 21:00:00.0",
}


def _revision(migration_path: Path) -> int:
    return int(migration_path.name.split("_", 1)[0])


def _seeded_table(migration_path: Path) -> str:
    """`53_seed_mfds_integration_field.py` -> `integration_field`."""
    return "integration_" + migration_path.stem.split("_integration_", 1)[1]


def _upgrade_body(source: str) -> str:
    """The `upgrade()` body of a migration, which is the only path a database took.

    A `downgrade` that deletes a row says nothing about what the migration did on the
    way up — reading the whole file made every seed with a cleanup downgrade look like
    a replace.
    """
    match = re.search(r"\ndef upgrade\(\)[^:]*:\n(.*?)(?=\ndef |\Z)", source, re.DOTALL)
    return match.group(1) if match else ""


def _way_up(source: str) -> str:
    """Everything a migration writes on the way up: the file before `def downgrade()`.

    Wider than `_upgrade_body` on purpose — seeds build their rows in module
    constants and helpers above `upgrade()`, and a code literal there is a row
    the upgrade inserts. What lies below is the reverse path: revision 119's
    downgrade re-seeds the operation row its upgrade retired, and reading that
    literal would have kept the operation alive at the very revision that
    removed it (`lib/backend-migration-policy.ts` skips the same calls).
    """
    downgrade_at = source.find("\ndef downgrade()")
    return source if downgrade_at < 0 else source[:downgrade_at]


# An upgrade that deletes an operation row by its id retires the operation
# (`lib/backend-migration-policy.ts` reads the same statement).
_RETIRES_OPERATION = r"\.delete\(\)\.where\([^)]*\.id\s*==\s*OPERATION_ID\)"


def _seed_owner(source: str) -> str | None:
    """The seed string a migration's rows belong to: its operation, else its provider.

    Both are `uuid5` seeds, which is how a file's rows are tied to the thing they
    configure without comparing derived ids.
    """
    for name in ("OPERATION_ID", "PROVIDER_ID"):
        match = re.search(rf'{name}\s*=\s*uuid5\([^,]+,\s*"([^"]+)"', source)
        if match:
            return match.group(1)
    return None


def _live_seed_owners(migrations_dir: Path) -> set[str]:
    """Seed owners the migration chain leaves alive.

    A provider `_replace_` (delete + insert in its **upgrade**) cascades every
    operation seeded before it — for that provider only. An operation erased that way
    has no row in any database, so replaying its seed describes a state that does not
    exist. An operation retired on its own — a revision that deletes its row by
    `OPERATION_ID` on the way up and seeds nothing in its place (119 for
    `search-barcode-item-info`) — is gone the same way.
    """
    owners: set[str] = set()
    provider_of: dict[str, str] = {}
    seeded_at: dict[str, int] = {}
    replaced_at: dict[str, int] = {}
    retired_at: dict[str, int] = {}
    for path in sorted(migrations_dir.glob("*.py"), key=_revision):
        source = path.read_text(encoding="utf-8")
        revision = _revision(path)
        tables = set(re.findall(r'table\(\s*"([a-z_]+)"', source))
        owner = _seed_owner(source)
        if owner is None:
            continue
        provider_match = re.search(r'PROVIDER_ID\s*=\s*uuid5\([^,]+,\s*"([^"]+)"', source)
        provider_seed = provider_match.group(1) if provider_match else None
        seeds_provider = "integration_provider" in tables
        replaces_provider = seeds_provider and ".delete()" in _upgrade_body(source)
        if replaces_provider and provider_seed is not None:
            replaced_at[provider_seed] = max(replaced_at.get(provider_seed, 0), revision)
        if not tables & {"integration_provider", "integration_operation"}:
            continue
        retires_operation = (
            "integration_operation" in tables
            and re.search(_RETIRES_OPERATION, _upgrade_body(source))
            and "op.bulk_insert(" not in _way_up(source)
        )
        if retires_operation:
            retired_at[owner] = max(retired_at.get(owner, 0), revision)
            continue
        owners.add(owner)
        seeded_at[owner] = revision
        if provider_seed is not None:
            provider_of[owner] = provider_seed
    return {
        owner
        for owner in owners
        if seeded_at[owner]
        >= max(replaced_at.get(provider_of.get(owner, owner), 0), retired_at.get(owner, 0))
    }


def _seed_family(migration_path: Path) -> str:
    """`67_seed_food_safety_korea_integration_field.py` -> `food_safety_korea`."""
    head = migration_path.stem.split("_integration_", 1)[0]
    return head.split("_", 2)[2]


def test_mfds_seed_migration_persists_executable_configuration() -> None:
    """Replay the live seeds, then assert the nutrition provider's configuration.

    Scope is deliberate: this test describes **the configuration the app executes
    today**, so it replays the newest live seed per owner and table (the shared
    `_replay_newest_integration_seeds`, which is also what the paging standard reads).
    It is not a history replay — revisions 29/31/32 write a column revision 50
    dropped, and an operation the provider cascade erased is not part of today's
    configuration. Those are covered by `test_every_seeded_operation_owns_a_request_file`.

    The replay is shared on purpose: this test used to carry its own copy, and the
    copy read "newest per table". The moment a second provider seeded the same tables,
    the copy replayed only the newer integration and this test asserted against a
    database where the nutrition provider had never been seeded.
    """
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            Base.metadata.create_all(connection)
            _replay_newest_integration_seeds(connection)

            seeded = (
                connection.execute(
                    sa.text(
                        "SELECT p.code AS provider_code, o.code AS operation_code, "
                        "o.response_root, "
                        "(SELECT count(*) FROM integration_secret WHERE provider_id = p.id) "
                        "AS secret_count, "
                        "(SELECT count(*) FROM integration_field "
                        "WHERE operation_id = o.id AND direction = 'REQUEST') "
                        "AS request_field_count, "
                        "(SELECT count(*) FROM integration_field "
                        "WHERE operation_id = o.id AND direction = 'RESPONSE') "
                        "AS response_field_count "
                        "FROM integration_provider AS p "
                        "JOIN integration_operation AS o ON o.provider_id = p.id "
                        "WHERE p.code = 'data-go-kr' "
                        "AND o.code = 'search-food-nutrition'"
                    )
                )
                .mappings()
                .one()
            )
            secret = (
                connection.execute(
                    sa.text(
                        "SELECT s.name, s.value, s.enabled FROM integration_secret AS s "
                        "JOIN integration_provider AS p ON p.id = s.provider_id "
                        "WHERE p.code = 'data-go-kr' AND s.name = 'service-key'"
                    )
                )
                .mappings()
                .one()
            )
            request_fields = (
                connection.execute(
                    sa.text(
                        "SELECT key, value_source, required, description, "
                        "secret_id IS NULL AS no_secret "
                        "FROM integration_field "
                        "WHERE direction = 'REQUEST' AND operation_id = "
                        "(SELECT id FROM integration_operation "
                        "WHERE code = 'search-food-nutrition') "
                        "ORDER BY ordinal"
                    )
                )
                .mappings()
                .all()
            )
            response_fields = (
                connection.execute(
                    sa.text(
                        "SELECT key, wire_path, value_type, required, description "
                        "FROM integration_field "
                        "WHERE direction = 'RESPONSE' AND operation_id = "
                        "(SELECT id FROM integration_operation "
                        "WHERE code = 'search-food-nutrition') "
                        "ORDER BY ordinal"
                    )
                )
                .mappings()
                .all()
            )

        assert dict(seeded) == {
            # Revision 74: one identity across all three columns - the portal
            # `apis.data.go.kr` is, and the dataset it serves.
            "provider_code": "data-go-kr",
            "operation_code": "search-food-nutrition",
            # The page, not its first record: /body/items/0 truncated every answer
            # to one row and made num_of_rows unobservable (58_replace_…_operation).
            "response_root": "/body/items",
            # Two credentials, not a pool: measured 2026-09-13, the first key
            # answers SERVICE_KEY_IS_NOT_REGISTERED_ERROR on the 수입식품 services
            # and the second answers them - a data.go.kr key carries the datasets
            # its own account applied for, so a field names the one its dataset
            # was approved under (revision 216).
            "secret_count": 2,
            "request_field_count": 11,
            "response_field_count": 193,
        }
        assert secret["name"] == "service-key"
        assert secret["enabled"] == 1
        assert len(secret["value"]) == 64
        assert [
            (field["key"], field["value_source"], field["required"], field["no_secret"])
            for field in request_fields
        ] == [
            ("service_key", "SECRET", 1, 0),
            # Paging is the caller's obligation, with no default anywhere:
            # 58_replace_mfds_integration_field made the pair CALLER + required,
            # and `_resolve_value` neither falls back to the field's value nor
            # lets the provider's default decide the window.
            ("page_no", "CALLER", 1, 1),
            ("num_of_rows", "CALLER", 1, 1),
            ("type", "LITERAL", 0, 1),
            ("food_name", "CALLER", 0, 1),
            ("research_ymd", "CALLER", 0, 1),
            ("maker_name", "CALLER", 0, 1),
            ("category_major_name", "CALLER", 0, 1),
            ("item_report_no", "CALLER", 0, 1),
            ("update_date", "CALLER", 0, 1),
            ("item_class_name", "CALLER", 0, 1),
        ]
        assert [field["description"] for field in request_fields[:2]] == [
            "인증키 (URL Encode) — 공공데이터포털에서 발급 받은 인증키",
            "페이지 번호 (예: 1) — 호출자가 반드시 전달한다",
        ]
        # Every provider column is configuration: the sheet's 193 rows, each with the
        # provider's own description. `wire_path` is relative to one element of the
        # page — the position is the operation's `response_root`, so no row repeats it
        # and no row pins an index. The key comes from the description, not the wire
        # name: 157 columns are `AMT_NUM<n>`, which names nothing.
        assert len(response_fields) == 193
        assert [field for field in response_fields if not field["description"]] == []
        assert [field["key"] for field in response_fields if field["required"]] == ["food_name"]
        for field in response_fields:
            assert field["value_type"] == "STRING", f"{field['key']} is not the sheet's 문자열"
            assert re.fullmatch(r"/[A-Z][A-Z0-9_]*", field["wire_path"]), (
                f"{field['key']} points at {field['wire_path']} — not an element-relative pointer"
            )
            assert re.fullmatch(r"[a-z][a-z0-9_]*", field["key"]), (
                f"{field['key']} is not snake case"
            )
            assert not field["key"].startswith("amt_num"), (
                f"{field['key']} carries the wire name: AMT_NUM<n> names nothing, the sheet does"
            )
        assert [
            (field["key"], field["wire_path"], field["description"])
            for field in response_fields[:3]
        ] == [
            ("row_no", "/NUM", "번호"),
            ("food_code", "/FOOD_CD", "식품코드"),
            ("food_name", "/FOOD_NM_KR", "식품명"),
        ]
        # The unit the sheet prints is the suffix, which is what keeps the pairs
        # apart: 리놀레산 ships in both (g) and (mg), 비타민 A in (μg RAE) and (μg).
        assert {
            field["wire_path"]: (field["key"], field["description"])
            for field in response_fields
            if field["wire_path"]
            in {"/AMT_NUM1", "/AMT_NUM13", "/AMT_NUM14", "/AMT_NUM15", "/AMT_NUM74", "/AMT_NUM75"}
        } == {
            "/AMT_NUM1": ("energy_kcal", "에너지(kcal)"),
            "/AMT_NUM13": ("sodium_mg", "나트륨(mg)"),
            "/AMT_NUM14": ("vitamin_a_ug_rae", "비타민 A(μg RAE)"),
            "/AMT_NUM15": ("vitamin_a_ug", "비타민 A(μg)"),
            "/AMT_NUM74": ("linoleic_acid_g", "리놀레산(18:2(n-6)c)(g)"),
            "/AMT_NUM75": ("linoleic_acid_mg", "리놀레산(18:2(n-6)c)(mg)"),
        }
    finally:
        engine.dispose()


def test_every_seeded_operation_owns_a_request_file() -> None:
    """A migration that seeds a **surviving** operation brings its request file.

    Discovery mirrors `lib/backend-migration-policy.ts` exactly, because two
    implementations reading the same migrations differently is how this gap opened
    in the first place:

      - by **target table**, never by filename — the filename rule read only
        `_integration_operation` files and, once any `_replace_` existed, dropped
        every `_seed_` one;
      - joining operation and field seeds through the shared `uuid5` seed string,
        since the id is derived and cannot be compared as a literal;
      - honouring the provider cascade **per provider**, and only when the upgrade
        replaces the row: `integration_operation.provider_id` is ON DELETE CASCADE, so
        an operation seeded before its own provider's `_replace_` is gone. Measured
        twice: `search-domestic-food-products` (revision 16) was erased by the
        nutrition provider replace at revision 20 and answers exactly like an
        operation that never existed; and reading `.delete()` anywhere in the file —
        including a `downgrade` that only cleans up — made the second provider's seed
        look like a replace that erased the first provider's operations;
      - honouring an operation's own retirement: a revision binding
        `integration_operation` whose upgrade deletes by `OPERATION_ID` ends every
        seed of that operation older than itself (revision 119 retired
        `search-barcode-item-info`, seeded at 72). A `_replace_` deletes and
        re-inserts in one upgrade, so its row is seeded *at* the retiring revision
        and survives the same `<`. Code literals are read from the way up only —
        the retiring revision's downgrade re-seeds the very row it took.
    """
    migrations_dir = Path(__file__).parents[2] / "alembic" / "versions"
    api_dir = Path(__file__).parents[3] / "api"
    seed_of: dict[str, str | None] = {}
    seeded_at: dict[str, int] = {}
    configured_seeds: set[str] = set()
    provider_of: dict[str, str | None] = {}
    provider_replaced_at: dict[str, int] = {}
    operation_retired_at: dict[str, int] = {}
    for path in sorted(migrations_dir.glob("*.py"), key=_revision):
        source = path.read_text(encoding="utf-8")
        revision = _revision(path)
        tables = set(re.findall(r'table\(\s*"([a-z_]+)"', source))
        seed_match = re.search(r'OPERATION_ID\s*=\s*uuid5\([^,]+,\s*"([^"]+)"', source)
        seed = seed_match.group(1) if seed_match else None
        provider_match = re.search(r'PROVIDER_ID\s*=\s*uuid5\([^,]+,\s*"([^"]+)"', source)
        provider_seed = provider_match.group(1) if provider_match else None
        if "integration_field" in tables and seed is not None:
            configured_seeds.add(seed)
        upgrade_body = _upgrade_body(source)
        if "integration_provider" in tables and ".delete()" in upgrade_body and provider_seed:
            provider_replaced_at[provider_seed] = max(
                provider_replaced_at.get(provider_seed, 0), revision
            )
        if "integration_operation" not in tables:
            continue
        if seed is not None and re.search(
            r"\.delete\(\)\.where\([^)]*\.id\s*==\s*OPERATION_ID\)", upgrade_body
        ):
            operation_retired_at[seed] = max(operation_retired_at.get(seed, 0), revision)
        for match in re.finditer(r'"code":\s*"([a-z0-9-]+)"', _way_up(source)):
            seed_of[match.group(1)] = seed
            seeded_at[match.group(1)] = revision
            provider_of[match.group(1)] = provider_seed
    for code, revision in seeded_at.items():
        replaced = provider_replaced_at.get(provider_of.get(code) or "", 0)
        retired = operation_retired_at.get(seed_of.get(code) or "", 0)
        if revision < max(replaced, retired):
            seed_of.pop(code, None)

    assert set(seed_of) == {
        "search-barcode-product-info",
        "search-common-standard",
        "search-common-standard-exclusion",
        "search-common-standard-type",
        "search-food-admin-disposition",
        "search-food-collection-inspection",
        "search-food-nutrition",
        "search-food-recall",
        "search-food-production",
        "search-livestock-production",
        "search-health-functional-production",
        "search-health-functional-item-report",
        "search-food-inspection-failure",
        "search-food-item-report",
        "search-food-qr-label",
        "search-food-qr-caution",
        "search-food-qr-manufacture",
        "search-food-qr-packaging",
        "search-food-qr-raw-material",
        "search-food-qr-storage",
        "search-haccp-label",
        "search-import-food-label",
        "search-food-qr-nutrition",
        "search-food-qr-allergy",
        "search-food-item-report-raw-material",
        "search-individual-standard",
        "search-livestock-item-report-raw-material",
        "search-product-classification",
        "search-food-raw-material",
        "search-test-item",
        "search-food-business",
        "search-food-business-site",
        "search-food-manufacturing-closure",
        "search-food-additive-manufacturing-closure",
        "search-food-import-business-closure",
        "search-food-health-functional-closure",
        "search-food-livestock-processing-closure",
        "search-food-meat-packaging-closure",
    }
    for code, seed in seed_of.items():
        request_file = api_dir / f"integration.{code}.http"
        assert request_file.exists(), f"{request_file.name} is missing for seeded operation {code}"
        assert f"/operations/{code}/execute" in request_file.read_text(encoding="utf-8")
        assert seed in configured_seeds, f"{code} has no live integration_field seed"


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "integration"


def _fixtures() -> list[Path]:
    return sorted(FIXTURE_DIR.glob("*.json"))


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_path", _fixtures(), ids=lambda path: path.stem)
async def test_execute_renders_the_seeded_contract(fixture_path: Path) -> None:
    """One measured exchange per operation, checked against the **seeded** rows.

    A hand-written contract test restates the configuration it is testing: the
    field list appears once in the seed migration and again in the test, and one
    operation cost 191 lines of it. Restating is not testing - the copy can agree
    with itself while disagreeing with the database - and it is the step a small
    model never reached in a measured run.

    So the rows come from the replayed seeds and only the *measured* part lives in
    the fixture: what the caller sent, what the provider answered, and what must
    therefore have left the process. Adding an operation means recording one
    exchange, not writing a test.
    """
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    operation_code = fixture_path.stem.split(".", 1)[0]
    configured = _client_from_seeds(operation_code, fixture)
    expected = cast(dict[str, object], fixture["expect"])
    inputs = cast(dict[str, object], fixture["inputs"])
    refusal = expected.get("raises")

    try:
        if refusal is not None:
            # A measured failure is as much of the contract as a measured page:
            # this provider answers HTTP 200 and states the real outcome in the
            # envelope, so a refusal is only visible if the wrapper is checked.
            with pytest.raises(IntegrationError, match=cast(str, refusal)):
                await configured.execute(inputs)
            return
        result = await configured.execute(inputs)
    finally:
        await configured.aclose()

    assert result.status_code == expected["status_code"]
    assert result.canonical_payload == expected["canonical_payload"]
    assert result.metadata == expected["metadata"]
    if "rows" in expected:
        # A file's execute is the download; its rows are what stream hands the
        # ledger, and a fixture that recorded them proves the reader on them.
        streamed = _client_from_seeds(operation_code, fixture)
        try:
            rows = [row async for chunk in streamed.stream(inputs) for row in chunk]
        finally:
            await streamed.aclose()
        assert rows == expected["rows"]


@pytest.mark.parametrize(
    ("match_mode", "expected_values", "value", "holds"),
    [
        ("PRESENT", None, "anything", True),
        ("PRESENT", None, None, False),
        ("EXACT", ["INFO-000"], "INFO-000", True),
        ("EXACT", ["INFO-000"], "INFO-200", False),
        ("EXACT", ["INFO-000", "INFO-200"], "INFO-000", False),
        ("ONE_OF", ["INFO-000", "INFO-200"], "INFO-200", True),
        ("ONE_OF", ["INFO-000", "INFO-200"], "ERROR-334", False),
    ],
)
def test_envelope_verdict_rules(
    match_mode: str, expected_values: list[str] | None, value: object, holds: bool
) -> None:
    """The verdict rules, stated once instead of per operation.

    A missing value is never a pass: an envelope key the provider did not send is
    the case where "no news is good news" silently accepts an error body. `EXACT`
    with two candidates is a configuration mistake, so it holds for neither -
    exactness with a choice is `ONE_OF` under another name.
    """
    field = IntegrationField(
        direction="RESPONSE",
        location="ENVELOPE",
        key="result_code",
        wire_path="/RESULT/CODE",
        value_type="STRING",
        required=True,
        match_mode=match_mode,
        expected_values=expected_values,
    )
    assert IntegrationClient._envelope_holds(field, value) is holds
    label = IntegrationClient._expected_label(field)
    assert label == ("any value" if match_mode == "PRESENT" else ", ".join(expected_values or []))


def _client_from_seeds(code: str, fixture: dict[str, object]) -> IntegrationClient:
    """The operation as the migrations seed it, wired to a recorded response.

    The transport asserts the request the seeded rows produced - path and query -
    because that is the half of the contract the provider would judge.
    """
    expected = cast(dict[str, object], fixture["expect"])
    recorded = cast(dict[str, object], fixture["response"])
    query = cast(dict[str, str], expected.get("query", {}))
    # A form screen's contract is its form: every part the browser posts, by name
    # and value, in a multipart body. Measured 2026-09-13 on impfood: one part
    # more or less than the screen's own JS sends is `302 -> /error/error`.
    form = cast(dict[str, str], expected.get("form", {}))
    bootstrap = cast(str | None, expected.get("bootstrap_path"))

    def handler(request: httpx2.Request) -> httpx2.Response:
        # The bootstrap is told from the call by its path, not its verb: a screen
        # read by GET (a detail lookup) has the same verb as the session fetch.
        if bootstrap is not None and request.url.path == bootstrap:
            return httpx2.Response(200, text="<html></html>", headers={"set-cookie": "S=1"})
        assert request.url.path == expected["path"], (
            f"{code}: rendered path {request.url.path} is not the measured {expected['path']}"
        )
        for name, value in query.items():
            assert request.url.params[name] == value, (
                f"{code}: query {name}={request.url.params.get(name)} is not the measured {value}"
            )
        if form:
            sent = _multipart_parts(request)
            assert sent == form, f"{code}: form parts {sent} are not the measured {form}"
        if "text" in recorded:
            return httpx2.Response(cast(int, recorded["status"]), text=cast(str, recorded["text"]))
        if "gzip_base64" in recorded:
            # A file door answers bytes, and the headers are part of what was
            # measured: the name the portal gave the file is read off them.
            return httpx2.Response(
                cast(int, recorded["status"]),
                content=base64.b64decode(cast(str, recorded["gzip_base64"])),
                headers=cast(dict[str, str], recorded.get("headers", {})),
            )
        return httpx2.Response(cast(int, recorded["status"]), json=recorded["json"])

    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            Base.metadata.create_all(connection)
            _replay_newest_integration_seeds(connection)
        with Session(engine) as session:
            seeded = session.execute(
                sa.select(IntegrationOperation)
                .where(IntegrationOperation.code == code)
                .options(
                    selectinload(IntegrationOperation.fields).selectinload(IntegrationField.secret),
                    selectinload(IntegrationOperation.provider),
                )
            ).scalar_one()
            secrets = cast(dict[str, str], fixture["secrets"])
            for field in seeded.fields:
                if field.secret is not None:
                    field.secret.value = secrets[field.secret.name]
            session.expunge_all()
    finally:
        engine.dispose()
    return IntegrationClient(
        operation=seeded,
        client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )


def _multipart_parts(request: httpx2.Request) -> dict[str, str]:
    """The (name, value) parts of a multipart body, in the order they were sent."""
    boundary = request.headers["content-type"].split("boundary=", 1)[1]
    parts: dict[str, str] = {}
    for chunk in request.content.decode("utf-8").split("--" + boundary)[1:-1]:
        head, _, value = chunk.partition("\r\n\r\n")
        name = head.split('name="', 1)[1].split('"', 1)[0]
        parts[name] = value.removesuffix("\r\n")
    return parts


def _replay_newest_integration_seeds(connection: sa.Connection) -> None:
    """Apply the newest live seed per (owner, table), then every correction, to a schema.

    A seed belongs to the operation it names, or to its provider when it names no
    operation. Only owners the migrations leave alive are replayed, and per owner only
    the newest file for each table — that is what makes a replay describe today's
    configuration rather than its history.

    Both halves were measured. Keeping the newest file per *table* replayed one
    integration and erased the other the moment a second provider landed. Keeping the
    newest per filename family resurrected `search-domestic-food-products` (revision
    16), an operation the provider replace at revision 20 had already cascaded away —
    and its row still writes a column revision 50 dropped.

    A `_correct_` revision is the third kind and is **cumulative**, not superseding: it
    UPDATEs columns of a row a seed already wrote, because a provider `_replace_`
    would cascade the operations away. Taking only the newest file per (owner, table)
    would therefore replay the correction *instead of* the seed and leave the row
    absent, so corrections are merged into the same revision-ordered run: newest seed
    first, then the corrections that landed after it. Revision 74 renamed this
    provider's `code` and `display_name`; without this the replayed database still
    answered `mfds-food-nutrition` while every real database answered
    `data-go-kr`, and the assertion below would have been green about a
    configuration that no longer exists.
    """
    migrations_dir = Path(__file__).parents[2] / "alembic" / "versions"
    live = _live_seed_owners(migrations_dir)
    newest: dict[tuple[str, str], Path] = {}
    for pattern in ("*_seed_*_integration_*.py", "*_replace_*_integration_*.py"):
        for path in migrations_dir.glob(pattern):
            table_name = _seeded_table(path)
            if table_name not in Base.metadata.tables:
                continue
            owner = _seed_owner(path.read_text(encoding="utf-8"))
            if owner is None or owner not in live:
                continue
            key = (owner, table_name)
            current = newest.get(key)
            if current is None or _revision(path) > _revision(current):
                newest[key] = path
    corrections = [
        path
        for path in migrations_dir.glob("*_correct_*_integration_*.py")
        if _seeded_table(path) in Base.metadata.tables
        and _seed_owner(path.read_text(encoding="utf-8")) in live
    ]
    migration_op = Operations(MigrationContext.configure(connection))
    for migration_path in sorted([*newest.values(), *corrections], key=_revision):
        spec = importlib.util.spec_from_file_location(migration_path.stem, migration_path)
        assert spec is not None
        assert spec.loader is not None
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        namespace = vars(migration)
        original_op = namespace["op"]
        namespace["op"] = migration_op
        try:
            upgrade = namespace["upgrade"]
            assert callable(upgrade)
            upgrade()
        finally:
            namespace["op"] = original_op


# The canonical paging inputs by family, mirroring PAGING_FAMILIES in
# app/core/integration.py and in .omp/hooks/lib/backend-migration-policy.ts. Wire names
# stay the provider's (`pageNo`/`numOfRows`, `startIdx`/`endIdx`); the caller-facing
# keys are ours. RANGE arrived with I1250, which has no page number at all — a second
# family is added by the first live operation that needs it, never before.
PAGING_FAMILIES = {
    "PAGE": frozenset({"page_no", "num_of_rows"}),
    "RANGE": frozenset({"range_start", "range_end"}),
}
PAGING_KEYS = frozenset(key for family in PAGING_FAMILIES.values() for key in family)


def test_paging_standard_holds_for_every_operation() -> None:
    """Paging is an endpoint setting, and a declared window is a whole window.

    Replaying the seeds is what makes this checkable: the rows carry
    `value_source`, `required` and `value`, so the standard can be asserted
    instead of pattern-matched. For every operation:

      - it declares a whole paging family, or none of it — a position without a
        size (or the reverse) is not a window;
      - every paging field is CALLER, required, and carries **no** default: a
        hidden default sends a window nobody asked for, and falling through to the
        provider's default makes the window unstated;
      - a paging operation's `response_root` must name the page and must not pin an
        index — `/body/items/0` returned one record however large the page was
        (measured). Mapping is the only response contract, so this root is also what
        the RESPONSE rows are resolved against, element by element.
    """
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            Base.metadata.create_all(connection)
            _replay_newest_integration_seeds(connection)
            operations = (
                connection.execute(
                    sa.text("SELECT id, code, response_root FROM integration_operation")
                )
                .mappings()
                .all()
            )
            fields = (
                connection.execute(
                    sa.text(
                        "SELECT operation_id, key, value_source, required, value "
                        "FROM integration_field WHERE direction = 'REQUEST'"
                    )
                )
                .mappings()
                .all()
            )
    finally:
        engine.dispose()

    assert operations, "no operation survived the replay — the standard would assert nothing"
    for operation in operations:
        own = [field for field in fields if field["operation_id"] == operation["id"]]
        keys = {field["key"] for field in own}
        declared = keys & PAGING_KEYS
        if not declared:
            continue
        family = next(
            (name for name, members in PAGING_FAMILIES.items() if declared == members), None
        )
        assert family is not None, (
            f"{operation['code']} declares {sorted(declared)}, which is not one whole family — "
            f"a window is a position and a size from the same family {sorted(PAGING_FAMILIES)}"
        )
        for field in own:
            if field["key"] not in PAGING_KEYS:
                continue
            assert field["value_source"] == "CALLER", f"{field['key']} is not caller-supplied"
            assert field["required"] == 1, f"{field['key']} is optional — an unstated window"
            assert field["value"] is None, f"{field['key']} carries a default"
        assert operation["response_root"] is not None, (
            f"{operation['code']} pages but names no page — every window needs a root"
        )
        assert not re.search(r"/\d+$", operation["response_root"]), (
            f"{operation['code']} pages but response_root {operation['response_root']} "
            "pins one record out of the page"
        )


def test_seeded_configuration_is_creatable_through_the_api() -> None:
    """Every seeded row must be a row the write path accepts.

    The four configuration tables have two writers: alembic seeds, and
    `POST/PUT /integration/`. A migration reaches the tables through the DB `CHECK`
    alone — it never meets the Pydantic literals or `IntegrationProviderService`'s validation.
    So a seeded shape the API refuses is a configuration **nobody can author or edit**:
    an operator reading it back and submitting one changed timeout is refused over a
    row they never touched, and the service's own rule becomes prose that guards
    nothing.

    Measured three times while this standard grew, each on the same axis — the DB and
    the runtime learned a new shape and the write-time validator did not:

      - `MAPPED` with a `response_root` (a page), refused as "mapped operations cannot
        carry a response root";
      - a `match_mode` on an `ENVELOPE` row, refused as "header matching applies to
        response headers only";
      - and the reverse — paging with no root, which the API allowed while the
        standard forbade it.

    This test runs both writers instead of reading them: it replays the live seeds,
    rebuilds the create request that would produce exactly those rows, and hands it to
    the same validation an API call gets. A third reader of the same invariant is how
    the first two divergences survived.
    """
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            Base.metadata.create_all(connection)
            _replay_newest_integration_seeds(connection)
            payloads = _seeded_create_requests(connection)
    finally:
        engine.dispose()

    assert payloads, "no provider survived the replay — this test would assert nothing"
    service = IntegrationProviderService(cast(AsyncSession, None))
    for payload in payloads:
        service._validate_create(payload)


def _seeded_create_requests(connection: sa.Connection) -> list[IntegrationCreateRequest]:
    """The create request that would produce the rows the seeds just wrote.

    Read from the replayed database, not from the migration source: the rows are the
    thing the API has to be able to express, and a reader of the seed files would be
    one more copy of the same invariant.
    """
    providers = (
        connection.execute(
            sa.text(
                "SELECT id, code, display_name, base_url, transport, bootstrap_path, enabled "
                "FROM integration_provider"
            )
        )
        .mappings()
        .all()
    )
    secrets = (
        connection.execute(
            sa.text(
                "SELECT id, provider_id, name, value, description, enabled FROM integration_secret"
            )
        )
        .mappings()
        .all()
    )
    operations = (
        connection.execute(
            sa.text(
                "SELECT id, provider_id, code, method, path_template, request_media_type, "
                "response_format, response_root, connect_timeout_ms, read_timeout_ms, max_retries, "
                "retry_base_ms, retry_max_ms, idempotent, request_schema, enabled "
                "FROM integration_operation"
            )
        )
        .mappings()
        .all()
    )
    fields = (
        connection.execute(
            sa.text(
                "SELECT operation_id, direction, location, key, wire_path, locator_kind, "
                "value_source, value, "
                "secret_id, value_type, format, required, description, sensitive, "
                "ordinal, enabled, "
                "match_mode, expected_values FROM integration_field ORDER BY ordinal"
            )
        )
        .mappings()
        .all()
    )
    secret_name_of = {secret["id"]: secret["name"] for secret in secrets}
    requests: list[IntegrationCreateRequest] = []
    for provider in providers:
        requests.append(
            IntegrationCreateRequest(
                code=provider["code"],
                display_name=provider["display_name"],
                base_url=provider["base_url"],
                transport=provider["transport"],
                bootstrap_path=provider["bootstrap_path"],
                enabled=bool(provider["enabled"]),
                secrets=[
                    IntegrationSecretCreateRequest(
                        name=secret["name"],
                        value=secret["value"],
                        description=secret["description"],
                        enabled=bool(secret["enabled"]),
                    )
                    for secret in secrets
                    if secret["provider_id"] == provider["id"]
                ],
                operations=[
                    IntegrationOperationCreateRequest(
                        code=operation["code"],
                        method=operation["method"],
                        path_template=operation["path_template"],
                        request_media_type=operation["request_media_type"],
                        response_format=operation["response_format"],
                        response_root=operation["response_root"],
                        connect_timeout_ms=operation["connect_timeout_ms"],
                        read_timeout_ms=operation["read_timeout_ms"],
                        max_retries=operation["max_retries"],
                        retry_base_ms=operation["retry_base_ms"],
                        retry_max_ms=operation["retry_max_ms"],
                        idempotent=bool(operation["idempotent"]),
                        request_schema=json.loads(operation["request_schema"])
                        if operation["request_schema"]
                        else None,
                        enabled=bool(operation["enabled"]),
                        fields=[
                            IntegrationFieldCreateRequest(
                                direction=field["direction"],
                                location=field["location"],
                                key=field["key"],
                                wire_path=field["wire_path"],
                                locator_kind=field["locator_kind"],
                                value_source=field["value_source"],
                                value=json.loads(field["value"]) if field["value"] else None,
                                secret_name=secret_name_of.get(field["secret_id"]),
                                value_type=field["value_type"],
                                format=field["format"],
                                required=bool(field["required"]),
                                description=field["description"],
                                sensitive=bool(field["sensitive"]),
                                ordinal=field["ordinal"],
                                enabled=bool(field["enabled"]),
                                match_mode=field["match_mode"],
                                expected_values=json.loads(field["expected_values"])
                                if field["expected_values"]
                                else None,
                            )
                            for field in fields
                            if field["operation_id"] == operation["id"]
                        ],
                    )
                    for operation in operations
                    if operation["provider_id"] == provider["id"]
                ],
            )
        )
    return requests
