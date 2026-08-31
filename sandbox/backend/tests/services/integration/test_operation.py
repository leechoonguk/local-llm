"""Integration operation service: behaviour the API and the transport depend on."""

from __future__ import annotations

from uuid import uuid4

import httpx2
import pytest

from app.core.exceptions import ConflictError, IntegrationConfigurationError, NotFoundError
from app.models.integration.provider import Integration
from app.schemas.integration.provider import IntegrationUpdateRequest
from app.services.integration.operation import IntegrationOperationService
from app.services.integration.provider import IntegrationProviderService
from tests.services.integration.helpers import configured_integration


@pytest.mark.asyncio
async def test_integration_service_rejects_conflicts_and_unavailable_operations(factory) -> None:
    """A duplicate code is a conflict, and a disabled provider is unavailable.

    Disabled is a configuration error rather than a 404 because the row exists
    and an operator, not the caller, has to act.
    """
    async with factory() as session:
        operation_service = IntegrationOperationService(session)
        provider_service = IntegrationProviderService(session)
        created = await provider_service.create_integration(configured_integration(), "tester")
        created_id = created.id
        await session.rollback()
        with pytest.raises(ConflictError):
            await provider_service.create_integration(configured_integration(), "tester")
        with pytest.raises(NotFoundError):
            await provider_service.update_integration(uuid4(), IntegrationUpdateRequest(), "tester")
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
            await operation_service.get_operation("disabled", "missing")


@pytest.mark.asyncio
async def test_integration_service_execute_operation_uses_shared_client(factory) -> None:
    """A supplied client is used and left open for the rest of the process.

    Closing the application client here would break every later request.
    """
    async with factory() as session:
        operation_service = IntegrationOperationService(session)
        provider_service = IntegrationProviderService(session)
        created = await provider_service.create_integration(configured_integration(), "tester")
        created_id = created.id
        await session.rollback()

        def handler(request: httpx2.Request) -> httpx2.Response:
            assert request.url.path == "/lookup/abc"
            return httpx2.Response(200, json={})

        shared = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        try:
            result = await operation_service.execute_operation(
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
        operation_service = IntegrationOperationService(session)
        provider_service = IntegrationProviderService(session)
        await provider_service.create_integration(configured_integration(), "tester")
        await session.rollback()

        def handler(request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(200, json={})

        real_client_cls = httpx2.AsyncClient
        monkeypatch.setattr(
            httpx2,
            "AsyncClient",
            lambda: real_client_cls(transport=httpx2.MockTransport(handler)),
        )
        result = await operation_service.execute_operation("catalog", "lookup", {"id": "abc"})
        assert result.status_code == 200


@pytest.mark.asyncio
async def test_integration_service_execute_operation_unavailable(factory) -> None:
    """An unknown operation code fails before any request is built."""
    async with factory() as session:
        operation_service = IntegrationOperationService(session)
        provider_service = IntegrationProviderService(session)
        await provider_service.create_integration(configured_integration(), "tester")
        await session.rollback()
        with pytest.raises(IntegrationConfigurationError):
            await operation_service.execute_operation("catalog", "missing", {})
