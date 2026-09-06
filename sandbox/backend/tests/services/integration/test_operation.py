"""Integration operation service: behaviour the API and the transport depend on.

`walk_operation` - the whole-feed walk the provider jobs read through - is
proven in `test_operation_walk.py`, and the key-pool rotation under it in
`test_operation_rotation.py`; this file is `get_operation`/`execute_operation`.
"""

from __future__ import annotations

from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import select

from app.core.exceptions import (
    ConflictError,
    IntegrationConfigurationError,
    IntegrationError,
    NotFoundError,
)
from app.core.integration import IntegrationClient
from app.models.integration.call import IntegrationCall
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
            result, call_id = await operation_service.execute_operation(
                "catalog", "lookup", {"id": "abc"}, actor="tester", client=shared
            )
        finally:
            await shared.aclose()
        assert result.status_code == 200
        assert result.canonical_payload == {}
        assert call_id is not None
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
        result, _call_id = await operation_service.execute_operation(
            "catalog", "lookup", {"id": "abc"}, actor="tester"
        )
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
            await operation_service.execute_operation("catalog", "missing", {}, actor="tester")


@pytest.mark.asyncio
async def test_execute_operation_logs_the_exchange(factory) -> None:
    """The call log is the only record of what left this process.

    Structured logs deliberately carry no bodies, so without this row an
    incident has the provider's verdict nowhere — which is what the
    `integration_call` table was created for and nothing wrote to.
    """
    async with factory() as session:
        operation_service = IntegrationOperationService(session)
        provider_service = IntegrationProviderService(session)
        await provider_service.create_integration(configured_integration(), "tester")
        await session.rollback()

        def handler(request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(200, json={})

        shared = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        try:
            await operation_service.execute_operation(
                "catalog", "lookup", {"id": "abc"}, actor="tester", client=shared
            )
        finally:
            await shared.aclose()

    async with factory() as session:
        calls = list((await session.execute(select(IntegrationCall))).scalars().all())

    assert len(calls) == 1
    assert calls[0].outcome == "SUCCESS"
    assert calls[0].provider_code == "catalog"
    assert calls[0].operation_code == "lookup"
    assert calls[0].status_code == 200
    assert calls[0].created_by == "tester"


@pytest.mark.asyncio
async def test_execute_operation_logs_a_refused_call_and_still_raises(factory) -> None:
    """A failure is logged and then re-raised, in that order.

    Logging only the happy path would leave the table empty for exactly the
    calls anyone opens it for; swallowing the error would leave the caller
    believing the provider answered.
    """
    async with factory() as session:
        operation_service = IntegrationOperationService(session)
        provider_service = IntegrationProviderService(session)
        await provider_service.create_integration(configured_integration(), "tester")
        await session.rollback()

        def handler(request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(500, text="upstream exploded")

        shared = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        try:
            with pytest.raises(IntegrationError):
                await operation_service.execute_operation(
                    "catalog", "lookup", {"id": "abc"}, actor="batch", client=shared
                )
        finally:
            await shared.aclose()

    async with factory() as session:
        calls = list((await session.execute(select(IntegrationCall))).scalars().all())

    assert [call.outcome for call in calls] == ["REFUSED"]
    assert calls[0].status_code == 500
    assert calls[0].error_code == "integration_error"
    assert calls[0].response_body is not None
    # The fixture operation allows one retry, so a retried call is recorded
    # as two attempts — the log answers "did we hammer them?" too.
    assert calls[0].attempts == 2


@pytest.mark.asyncio
async def test__create_call_log_without_an_exchange_writes_nothing(factory) -> None:
    """A client that never executed has nothing to record.

    The log is written from a `finally`, so it also runs when the failure
    happened before any request left — and an empty row would be a call that
    never occurred.
    """
    async with factory() as session:
        operation_service = IntegrationOperationService(session)
        provider_service = IntegrationProviderService(session)
        await provider_service.create_integration(configured_integration(), "tester")
        await session.rollback()
        client = await IntegrationClient.from_database(
            session=session, provider_code="catalog", operation_code="lookup"
        )
        await operation_service._create_call_log(client, "tester")
        await client.aclose()

    async with factory() as session:
        assert (await session.execute(select(IntegrationCall))).scalars().all() == []
