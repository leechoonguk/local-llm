"""Integration call service: the log a provider's screen reads."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.repositories.integration.call import IntegrationCallRepository
from app.schemas.integration.call import IntegrationCallCreateInternal
from app.services.integration.call import IntegrationCallService
from app.services.integration.provider import IntegrationProviderService
from tests.services.integration.helpers import configured_integration


def logged_call(provider_code: str, operation_code: str) -> IntegrationCallCreateInternal:
    """One answered call, as the client records it after an exchange."""
    return IntegrationCallCreateInternal(
        provider_code=provider_code,
        operation_code=operation_code,
        method="GET",
        url=f"https://api.example/{operation_code}",
        request_headers={"accept": "application/json"},
        status_code=200,
        outcome="SUCCESS",
        duration_ms=12,
        attempts=1,
        created_by="tester",
    )


@pytest.mark.asyncio
async def test_calls_are_read_per_provider_newest_first(factory) -> None:
    """The page answers "what did *this* provider send, last first".

    Another provider's calls live in the same table and the log is keyed on the
    provider's code, so a read without that predicate would show a neighbour's
    traffic under this row — and an ascending order would put page one on the
    oldest call, which is never the one being asked about.
    """
    async with factory() as session:
        provider_service = IntegrationProviderService(session)
        mine = await provider_service.create_integration(configured_integration(), "tester")
        provider_id, provider_code = mine.id, mine.code
        await session.rollback()
        theirs = await provider_service.create_integration(
            configured_integration(code="other"), "tester"
        )
        other_code = theirs.code
        await session.rollback()

        calls = IntegrationCallRepository(session)
        for operation in ("first", "second"):
            await calls.create(logged_call(provider_code, operation))
        await calls.create(logged_call(other_code, "elsewhere"))
        await session.commit()

    async with factory() as session:
        service = IntegrationCallService(session)
        page = [call.operation_code for call in await service.list_provider_calls(provider_id)]
        total = await service.count_provider_calls(provider_id)

    assert page == ["second", "first"]
    assert total == 2


@pytest.mark.asyncio
async def test_calls_page_within_one_provider(factory) -> None:
    """The window is the caller's, and the total describes the unwindowed set."""
    async with factory() as session:
        created = await IntegrationProviderService(session).create_integration(
            configured_integration(), "tester"
        )
        provider_id, provider_code = created.id, created.code
        await session.rollback()
        calls = IntegrationCallRepository(session)
        for operation in ("first", "second", "third"):
            await calls.create(logged_call(provider_code, operation))
        await session.commit()

    async with factory() as session:
        service = IntegrationCallService(session)
        window = [
            call.operation_code for call in await service.list_provider_calls(provider_id, 1, 1)
        ]
        total = await service.count_provider_calls(provider_id)

    assert window == ["second"]
    assert total == 3


@pytest.mark.asyncio
async def test_unknown_provider_is_not_an_empty_log(factory) -> None:
    """An id nobody configured answers 404, not a page that reads as "never called"."""
    async with factory() as session:
        service = IntegrationCallService(session)
        with pytest.raises(NotFoundError):
            await service.list_provider_calls(uuid4())
        with pytest.raises(NotFoundError):
            await service.count_provider_calls(uuid4())
