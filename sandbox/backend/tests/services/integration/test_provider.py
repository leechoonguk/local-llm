"""Integration provider service: behaviour the API and the transport depend on."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import IntegrationConfigurationError, NotFoundError
from app.schemas.integration.provider import IntegrationUpdateRequest
from app.schemas.integration.secret import IntegrationSecretCreateRequest
from app.services.integration.operation import IntegrationOperationService
from app.services.integration.provider import IntegrationProviderService
from tests.services.integration.helpers import (
    configured_integration,
    configured_operation,
    request_field,
    response_field,
)


@pytest.mark.asyncio
async def test_integration_service_crud_and_runtime_lookup(factory) -> None:
    """The stored configuration is what the runtime lookup resolves.

    The update replaces the operation list with an empty one: a merge instead
    of a replace would leave a retired operation callable.
    """
    async with factory() as session:
        operation_service = IntegrationOperationService(session)
        provider_service = IntegrationProviderService(session)
        created = await provider_service.create_integration(configured_integration(), "tester")
        created_id = created.id
        await session.rollback()
        assert (await provider_service.get_integration(created_id)).code == "catalog"
        await session.rollback()
        assert len(await provider_service.list_integrations()) == 1
        await session.rollback()
        await session.rollback()
        operation = await operation_service.get_operation("catalog", "lookup")
        assert operation.code == "lookup"
        await session.rollback()

        updated = await provider_service.update_integration(
            created_id,
            IntegrationUpdateRequest(display_name="Catalog v2", operations=[]),
            "tester",
        )
        assert updated.display_name == "Catalog v2"
        assert updated.operations == []
        updated_id = updated.id
        await session.rollback()
        await provider_service.delete_integration(updated_id)
        with pytest.raises(NotFoundError):
            await provider_service.get_integration(updated_id)


def test_integration_service_validates_configuration_boundaries() -> None:
    """Every stored value that the transport trusts is rejected here if invalid.

    A base URL with a path, a relative template, a timeout below the floor, or
    a schema with an external `$ref` would each become a runtime failure or an
    outbound fetch, so they are refused at write time.
    """
    service = IntegrationProviderService(cast(AsyncSession, None))
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
    service = IntegrationProviderService(cast(AsyncSession, None))
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
    service = IntegrationProviderService(cast(AsyncSession, None))
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
    service = IntegrationProviderService(cast(AsyncSession, None))
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
    service = IntegrationProviderService(cast(AsyncSession, None))
    with pytest.raises(IntegrationConfigurationError, match="never carry a value source"):
        service._validate_response_field(response_field(value_source="CALLER"))
    with pytest.raises(IntegrationConfigurationError, match="key is invalid"):
        service._validate_response_field(response_field(key="Bad"))
    with pytest.raises(IntegrationConfigurationError, match="JSON Pointer"):
        service._validate_response_field(response_field(wire_path="invalid"))
    with pytest.raises(IntegrationConfigurationError, match="header name is invalid"):
        service._validate_response_field(response_field(location="HEADER", wire_path="bad header"))
    with pytest.raises(IntegrationConfigurationError, match="body or a header only"):
        service._validate_response_field(response_field(location="QUERY", wire_path="q"))


def test_integration_service_validates_value_matching() -> None:
    """A match mode and its expected values must agree, or the check is a no-op.

    EXACT with no values would silently accept anything; IGNORE with values would
    mislead the next reader. Two locations may carry a mode — a response header and a
    response ENVELOPE row — because both are values the provider chose; a REQUEST row
    or a mapped BODY row carrying one is a claim nothing enforces.
    """
    service = IntegrationProviderService(cast(AsyncSession, None))
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
    service = IntegrationProviderService(cast(AsyncSession, None))
    duplicate = IntegrationSecretCreateRequest(name="api-key", value="v")
    with pytest.raises(IntegrationConfigurationError, match="Secret names must be unique"):
        service._validate_create(configured_integration(secrets=[duplicate, duplicate]))


def test_integration_service_accepts_request_schema_operation() -> None:
    """A local schema is accepted — validation must not reject every schema."""
    service = IntegrationProviderService(cast(AsyncSession, None))
    service._validate_operation(configured_operation(request_schema={"type": "object"}), set())


@pytest.mark.asyncio
async def test_integration_service_delete_missing(factory) -> None:
    """Deleting an absent provider is 404, not a silent success."""
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await IntegrationProviderService(session).delete_integration(uuid4())


@pytest.mark.asyncio
async def test_count_integrations_ignores_the_window(factory) -> None:
    """The total is the collection's size, not the page's.

    `list_integrations` eager-loads operations and secrets; a count written as
    `len(await list_integrations())` would load that whole graph to produce one
    integer, so this asserts the number while the page holds only one row.
    """
    async with factory() as session:
        service = IntegrationProviderService(session)
        for code in ("alpha", "beta", "gamma"):
            await service.create_integration(configured_integration(code=code), "tester")
            await session.rollback()

    async with factory() as session:
        service = IntegrationProviderService(session)
        page = await service.list_integrations(offset=2, limit=1)
        await session.rollback()
        total = await service.count_integrations()

    assert len(page) == 1
    assert total == 3
