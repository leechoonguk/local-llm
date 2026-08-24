"""IntegrationService: CRUD, configuration validation, and secret lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, IntegrationConfigurationError, NotFoundError
from app.models.integration import Integration
from app.schemas.integration import (
    IntegrationCreateRequest,
    IntegrationFieldCreateRequest,
    IntegrationOperationCreateRequest,
    IntegrationSecretCreateRequest,
    IntegrationUpdateRequest,
)
from app.services.integration import IntegrationService


def configured_operation(**updates: object) -> IntegrationOperationCreateRequest:
    """A valid operation, so each test can invalidate exactly one thing."""
    values: dict[str, object] = {
        "code": "lookup",
        "method": "GET",
        "path_template": "/lookup/{id}",
        "connect_timeout_ms": 10,
        "read_timeout_ms": 20,
        "max_retries": 1,
        "retry_base_ms": 1,
        "retry_max_ms": 2,
        "idempotent": True,
        "fields": [
            {
                "direction": "REQUEST",
                "location": "PATH",
                "key": "id",
                "wire_path": "id",
                "value_source": "CALLER",
                "value_type": "STRING",
                "required": True,
            }
        ],
    }
    values.update(updates)
    return IntegrationOperationCreateRequest.model_validate(values)


def configured_integration(**updates: object) -> IntegrationCreateRequest:
    """A valid provider carrying one operation."""
    values: dict[str, object] = {
        "code": "catalog",
        "display_name": "Catalog",
        "base_url": "https://catalog.example.com",
        "operations": [configured_operation()],
    }
    values.update(updates)
    return IntegrationCreateRequest.model_validate(values)


def request_field(**updates: object) -> IntegrationFieldCreateRequest:
    """A valid outbound field to mutate one attribute of at a time."""
    values: dict[str, object] = {
        "direction": "REQUEST",
        "location": "QUERY",
        "key": "query",
        "wire_path": "query",
        "value_source": "CALLER",
        "value_type": "STRING",
        "required": True,
    }
    values.update(updates)
    return IntegrationFieldCreateRequest.model_validate(values)


def response_field(**updates: object) -> IntegrationFieldCreateRequest:
    """A valid inbound body field to mutate one attribute of at a time."""
    values: dict[str, object] = {
        "direction": "RESPONSE",
        "location": "BODY",
        "key": "result",
        "wire_path": "/result",
        "value_type": "STRING",
        "required": True,
    }
    values.update(updates)
    return IntegrationFieldCreateRequest.model_validate(values)


@pytest.mark.asyncio
async def test_integration_service_crud_and_runtime_lookup(factory) -> None:
    """The stored configuration is what the runtime lookup resolves.

    The update replaces the operation list with an empty one: a merge instead
    of a replace would leave a retired operation callable.
    """
    async with factory() as session:
        service = IntegrationService(session)
        created = await service.create_integration(configured_integration(), "tester")
        created_id = created.id
        await session.rollback()
        assert (await service.get_integration(created_id)).code == "catalog"
        await session.rollback()
        assert len(await service.list_integrations()) == 1
        await session.rollback()
        assert len(await service.find_stale(datetime.now(UTC) + timedelta(days=1))) == 1
        await session.rollback()
        operation = await service.get_operation("catalog", "lookup")
        assert operation.code == "lookup"
        await session.rollback()

        updated = await service.update_integration(
            created_id,
            IntegrationUpdateRequest(display_name="Catalog v2", operations=[]),
            "tester",
        )
        assert updated.display_name == "Catalog v2"
        assert updated.operations == []
        updated_id = updated.id
        await session.rollback()
        await service.delete_integration(updated_id)
        with pytest.raises(NotFoundError):
            await service.get_integration(updated_id)


@pytest.mark.asyncio
async def test_integration_service_rejects_conflicts_and_unavailable_operations(factory) -> None:
    """A duplicate code is a conflict, and a disabled provider is unavailable.

    Disabled is a configuration error rather than a 404 because the row exists
    and an operator, not the caller, has to act.
    """
    async with factory() as session:
        service = IntegrationService(session)
        created = await service.create_integration(configured_integration(), "tester")
        created_id = created.id
        await session.rollback()
        with pytest.raises(ConflictError):
            await service.create_integration(configured_integration(), "tester")
        with pytest.raises(NotFoundError):
            await service.update_integration(uuid4(), IntegrationUpdateRequest(), "tester")
        assert created_id is not None
        provider = Integration(
            code="disabled",
            display_name="Disabled",
            base_url="https://disabled.example.com",
            enabled=False,
            operations=[],
        )
        session.add(provider)
        await session.commit()
        with pytest.raises(IntegrationConfigurationError):
            await service.get_operation("disabled", "missing")


def test_integration_service_validates_configuration_boundaries() -> None:
    """Every stored value that the transport trusts is rejected here if invalid.

    A base URL with a path, a relative template, a timeout below the floor, or
    a schema with an external `$ref` would each become a runtime failure or an
    outbound fetch, so they are refused at write time.
    """
    service = IntegrationService(cast(AsyncSession, None))
    with pytest.raises(IntegrationConfigurationError):
        service._validate_provider("UPPER", "https://example.com")
    with pytest.raises(IntegrationConfigurationError):
        service._validate_base_url("https://example.com/path")
    with pytest.raises(IntegrationConfigurationError):
        service._validate_operations([configured_operation(), configured_operation()], set())
    with pytest.raises(IntegrationConfigurationError):
        service._validate_operation(configured_operation(path_template="relative"), set())
    with pytest.raises(IntegrationConfigurationError):
        service._validate_operation(configured_operation(read_timeout_ms=1), set())
    with pytest.raises(IntegrationConfigurationError):
        service._validate_operation(
            configured_operation().model_copy(update={"retry_max_ms": 0}), set()
        )
    with pytest.raises(IntegrationConfigurationError):
        service._validate_schema({"$ref": "https://example.com/schema"}, "Request schema")
    with pytest.raises(IntegrationConfigurationError):
        service._validate_schema({"type": 1}, "Request schema")
    assert service._contains_external_ref({"items": [{"$ref": "#/local"}]}) is False
    assert service._contains_external_ref({"items": [{"$ref": "https://external"}]}) is True
    service._validate_update(IntegrationUpdateRequest(), set())
    service._validate_update(
        IntegrationUpdateRequest(base_url="https://example.com", operations=[]), set()
    )


def test_integration_service_validates_response_root() -> None:
    """Mapping is the only contract, so the root carries the whole decision."""
    service = IntegrationService(cast(AsyncSession, None))
    with pytest.raises(IntegrationConfigurationError, match="must be a JSON Pointer"):
        service._validate_response_root(configured_operation(response_root="body/items"))
    # An index pin returned one record however large the page was — measured.
    with pytest.raises(IntegrationConfigurationError, match="not one record in it"):
        service._validate_response_root(configured_operation(response_root="/body/items/0"))
    # A paging operation that names no page cannot return the window it was asked for.
    with pytest.raises(IntegrationConfigurationError, match="must name the page"):
        service._validate_response_root(
            configured_operation(
                response_root=None,
                fields=[
                    request_field(key="page_no", wire_path="pageNo"),
                    request_field(key="num_of_rows", wire_path="numOfRows"),
                ],
            )
        )
    # Half a family, or two families at once, is not a window.
    with pytest.raises(IntegrationConfigurationError, match="not one whole family"):
        service._validate_response_root(
            configured_operation(
                response_root="/body/items",
                fields=[request_field(key="page_no", wire_path="pageNo")],
            )
        )
    with pytest.raises(IntegrationConfigurationError, match="not one whole family"):
        service._validate_response_root(
            configured_operation(
                response_root="/body/items",
                fields=[
                    request_field(key="page_no", wire_path="pageNo"),
                    request_field(key="range_end", wire_path="endIdx"),
                ],
            )
        )
    # RANGE is the second family: a row interval, which is how I1250 pages.
    service._validate_response_root(
        configured_operation(
            response_root="/I1250/row",
            fields=[
                request_field(key="range_start", wire_path="startIdx"),
                request_field(key="range_end", wire_path="endIdx"),
            ],
        )
    )
    service._validate_response_root(
        configured_operation(
            response_root="/body/items",
            fields=[
                request_field(key="page_no", wire_path="pageNo"),
                request_field(key="num_of_rows", wire_path="numOfRows"),
            ],
        )
    )
    # No paging inputs: mapping one record through absolute pointers stays legal.
    service._validate_response_root(configured_operation(response_root=None))


def test_integration_service_validates_field_sources() -> None:
    """A value source must be resolvable before the operation is stored.

    An unknown secret name or context key would otherwise send an empty value
    and read as a provider authorization failure.
    """
    service = IntegrationService(cast(AsyncSession, None))
    with pytest.raises(IntegrationConfigurationError, match="need a value source"):
        service._validate_source(
            response_field().model_copy(update={"direction": "REQUEST"}), set()
        )
    with pytest.raises(IntegrationConfigurationError, match="reference a provider secret by name"):
        service._validate_source(request_field(value_source="SECRET"), set())
    with pytest.raises(IntegrationConfigurationError, match="Unknown provider secret"):
        service._validate_source(
            request_field(value_source="SECRET", secret_name="absent"), {"present"}
        )
    with pytest.raises(IntegrationConfigurationError, match="Only SECRET fields"):
        service._validate_source(request_field(secret_name="api-key"), {"api-key"})
    with pytest.raises(IntegrationConfigurationError, match="Literal fields need a value"):
        service._validate_source(request_field(value_source="LITERAL"), set())
    with pytest.raises(IntegrationConfigurationError, match="Unknown request context key"):
        service._validate_source(request_field(value_source="CONTEXT"), set())
    service._validate_source(request_field(value_source="CONTEXT", key="request_id"), set())


def test_integration_service_validates_field_uniqueness_and_placement() -> None:
    """Duplicate keys and body fields without a schema are refused.

    Reserved headers are rejected too: letting configuration set `host` or
    `x-request-id` would break routing and tracing.
    """
    service = IntegrationService(cast(AsyncSession, None))
    duplicate = request_field()
    with pytest.raises(IntegrationConfigurationError, match="unique per direction"):
        service._validate_fields(configured_operation(fields=[duplicate, duplicate]), set())
    with pytest.raises(IntegrationConfigurationError, match="JSON Pointer"):
        service._validate_fields(
            configured_operation(fields=[request_field(location="BODY", wire_path="body")]), set()
        )
    with pytest.raises(IntegrationConfigurationError, match="require a request schema"):
        service._validate_fields(
            configured_operation(fields=[request_field(location="BODY", wire_path="/body")]), set()
        )
    with pytest.raises(IntegrationConfigurationError, match="Request field path is invalid"):
        service._validate_fields(
            configured_operation(fields=[request_field(wire_path="bad path")]), set()
        )
    with pytest.raises(IntegrationConfigurationError):
        service._validate_request_header("x-request-id", "CALLER", False)
    with pytest.raises(IntegrationConfigurationError):
        service._validate_request_header("host", "CALLER", False)
    with pytest.raises(IntegrationConfigurationError):
        service._validate_request_header("x-api-key", "LITERAL", False)


def test_integration_service_validates_response_fields() -> None:
    """Inbound fields carry no source and live in the body or a header only.

    The key becomes a caller-facing name, so its spelling is part of the API.
    """
    service = IntegrationService(cast(AsyncSession, None))
    with pytest.raises(IntegrationConfigurationError, match="never carry a value source"):
        service._validate_response_field(response_field(value_source="CALLER"))
    with pytest.raises(IntegrationConfigurationError, match="key is invalid"):
        service._validate_response_field(response_field(key="Bad"))
    with pytest.raises(IntegrationConfigurationError, match="JSON Pointer"):
        service._validate_response_field(response_field(wire_path="invalid"))
    with pytest.raises(IntegrationConfigurationError, match="header name is invalid"):
        service._validate_response_field(
            response_field(location="HEADER", wire_path="bad header")
        )
    with pytest.raises(IntegrationConfigurationError, match="body or a header only"):
        service._validate_response_field(response_field(location="QUERY", wire_path="q"))


def test_integration_service_validates_value_matching() -> None:
    """A match mode and its expected values must agree, or the check is a no-op.

    EXACT with no values would silently accept anything; IGNORE with values would
    mislead the next reader. Two locations may carry a mode — a response header and a
    response ENVELOPE row — because both are values the provider chose; a REQUEST row
    or a mapped BODY row carrying one is a claim nothing enforces.
    """
    service = IntegrationService(cast(AsyncSession, None))
    header = response_field(location="HEADER", wire_path="x-mode", key="mode")
    envelope = response_field(location="ENVELOPE", wire_path="/RESULT/CODE", key="result_code")
    with pytest.raises(IntegrationConfigurationError, match="headers and envelopes only"):
        service._validate_match(request_field(match_mode="EXACT"))
    with pytest.raises(IntegrationConfigurationError, match="headers and envelopes only"):
        service._validate_match(
            response_field(location="BODY", wire_path="/name", key="name", match_mode="EXACT")
        )
    with pytest.raises(IntegrationConfigurationError, match="do not match the field's mode"):
        service._validate_match(header.model_copy(update={"match_mode": "EXACT"}))
    with pytest.raises(IntegrationConfigurationError, match="do not match the field's mode"):
        service._validate_match(header.model_copy(update={"match_mode": "ONE_OF"}))
    with pytest.raises(IntegrationConfigurationError, match="do not match the field's mode"):
        service._validate_match(
            header.model_copy(update={"match_mode": "IGNORE", "expected_values": ["a"]})
        )
    service._validate_match(
        header.model_copy(update={"match_mode": "EXACT", "expected_values": ["a"]})
    )
    # The envelope verdict the seeded I1250 operation carries: one of the codes that
    # mean the provider served the request.
    service._validate_match(
        envelope.model_copy(
            update={"match_mode": "ONE_OF", "expected_values": ["INFO-000", "INFO-200"]}
        )
    )
    # An envelope row with no mode is metadata, not a claim — total_count rides this way.
    service._validate_match(envelope)


def test_integration_service_rejects_duplicate_secret_names() -> None:
    """Names are how fields reference secrets, so a duplicate is ambiguous."""
    service = IntegrationService(cast(AsyncSession, None))
    duplicate = IntegrationSecretCreateRequest(name="api-key", value="v")
    with pytest.raises(IntegrationConfigurationError, match="Secret names must be unique"):
        service._validate_create(configured_integration(secrets=[duplicate, duplicate]))


@pytest.mark.asyncio
async def test_integration_service_secret_lifecycle(factory) -> None:
    """A secret is created, listed, and protected while a field references it."""
    secret = IntegrationSecretCreateRequest(name="api-key", value="issued")
    field = request_field(value_source="SECRET", secret_name="api-key", key="api_key")
    payload = configured_integration(
        secrets=[secret], operations=[configured_operation(fields=[field])]
    )
    async with factory() as session:
        service = IntegrationService(session)
        provider = await service.create_integration(payload, "tester")
        provider_id = provider.id
        await session.rollback()

        added = await service.create_secret(
            provider_id, IntegrationSecretCreateRequest(name="second", value="v2"), "tester"
        )
        assert added.name == "second"
        await session.rollback()

        assert [row.name for row in await service.list_secrets(provider_id)] == [
            "api-key",
            "second",
        ]
        await session.rollback()

        with pytest.raises(ConflictError, match="already exists"):
            await service.create_secret(
                provider_id, IntegrationSecretCreateRequest(name="second", value="v3"), "tester"
            )
        await session.rollback()

        # The unreferenced secret goes; the one the request field names is protected.
        await service.delete_secret(provider_id, "second")
        await session.rollback()
        with pytest.raises(ConflictError, match="still referenced"):
            await service.delete_secret(provider_id, "api-key")
        await session.rollback()
        with pytest.raises(NotFoundError):
            await service.delete_secret(provider_id, "absent")
        await session.rollback()
        with pytest.raises(NotFoundError):
            await service.list_secrets(uuid4())


@pytest.mark.asyncio
async def test_integration_service_delete_missing(factory) -> None:
    """Deleting an absent provider is 404, not a silent success."""
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await IntegrationService(session).delete_integration(uuid4())


def test_integration_service_accepts_request_schema_operation() -> None:
    """A local schema is accepted — validation must not reject every schema."""
    service = IntegrationService(cast(AsyncSession, None))
    service._validate_operation(configured_operation(request_schema={"type": "object"}), set())


@pytest.mark.asyncio
async def test_integration_service_execute_operation_uses_shared_client(factory) -> None:
    """A supplied client is used and left open for the rest of the process.

    Closing the application client here would break every later request.
    """
    async with factory() as session:
        service = IntegrationService(session)
        created = await service.create_integration(configured_integration(), "tester")
        created_id = created.id
        await session.rollback()

        def handler(request: httpx2.Request) -> httpx2.Response:
            assert request.url.path == "/lookup/abc"
            return httpx2.Response(200, json={})

        shared = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        try:
            result = await service.execute_operation(
                "catalog", "lookup", {"id": "abc"}, client=shared
            )
        finally:
            await shared.aclose()
        assert result.status_code == 200
        assert result.canonical_payload == {}
        assert created_id is not None


@pytest.mark.asyncio
async def test_integration_service_execute_operation_owns_its_client(
    factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a supplied client the service creates and closes its own.

    That is the batch/CLI path, where no application lifespan owns a client;
    leaking it there leaks a socket per call.
    """
    async with factory() as session:
        service = IntegrationService(session)
        await service.create_integration(configured_integration(), "tester")
        await session.rollback()

        def handler(request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(200, json={})

        real_client_cls = httpx2.AsyncClient
        monkeypatch.setattr(
            httpx2,
            "AsyncClient",
            lambda: real_client_cls(transport=httpx2.MockTransport(handler)),
        )
        result = await service.execute_operation("catalog", "lookup", {"id": "abc"})
        assert result.status_code == 200


@pytest.mark.asyncio
async def test_integration_service_execute_operation_unavailable(factory) -> None:
    """An unknown operation code fails before any request is built."""
    async with factory() as session:
        service = IntegrationService(session)
        await service.create_integration(configured_integration(), "tester")
        await session.rollback()
        with pytest.raises(IntegrationConfigurationError):
            await service.execute_operation("catalog", "missing", {})
