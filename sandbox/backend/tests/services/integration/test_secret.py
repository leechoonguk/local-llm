"""Integration secret service: behaviour the API and the transport depend on."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.integration.secret import (
    IntegrationSecretCreateRequest,
    IntegrationSecretUpdateRequest,
)
from app.services.integration.provider import IntegrationProviderService
from app.services.integration.secret import IntegrationSecretService
from tests.services.integration.helpers import (
    configured_integration,
    configured_operation,
    request_field,
)


@pytest.mark.asyncio
async def test_integration_service_secret_lifecycle(factory) -> None:
    """A secret is created, listed, and protected while a field references it."""
    secret = IntegrationSecretCreateRequest(name="api-key", value="issued")
    field = request_field(value_source="SECRET", secret_name="api-key", key="api_key")
    payload = configured_integration(
        secrets=[secret], operations=[configured_operation(fields=[field])]
    )
    async with factory() as session:
        provider_service = IntegrationProviderService(session)
        secret_service = IntegrationSecretService(session)
        provider = await provider_service.create_integration(payload, "tester")
        provider_id = provider.id
        await session.rollback()

        added = await secret_service.create_secret(
            provider_id, IntegrationSecretCreateRequest(name="second", value="v2"), "tester"
        )
        assert added.name == "second"
        await session.rollback()

        assert [row.name for row in await secret_service.list_secrets(provider_id)] == [
            "api-key",
            "second",
        ]
        await session.rollback()

        with pytest.raises(ConflictError, match="already exists"):
            await secret_service.create_secret(
                provider_id, IntegrationSecretCreateRequest(name="second", value="v3"), "tester"
            )
        await session.rollback()

        # The unreferenced secret goes; the one the request field names is protected.
        await secret_service.delete_secret(provider_id, "second")
        await session.rollback()
        with pytest.raises(ConflictError, match="still referenced"):
            await secret_service.delete_secret(provider_id, "api-key")
        await session.rollback()
        with pytest.raises(NotFoundError):
            await secret_service.delete_secret(provider_id, "absent")
        await session.rollback()
        with pytest.raises(NotFoundError):
            await secret_service.list_secrets(uuid4())


@pytest.mark.asyncio
async def test_integration_service_secret_update_keeps_absent_value(factory) -> None:
    """A rotation replaces the value; an edit without one keeps what is stored.

    The value is write-only, so a client relabelling a credential cannot resend it —
    an omitted `value` has to mean "keep", never "clear".
    """
    async with factory() as session:
        provider_service = IntegrationProviderService(session)
        secret_service = IntegrationSecretService(session)
        provider = await provider_service.create_integration(
            configured_integration(
                secrets=[IntegrationSecretCreateRequest(name="api-key", value="issued")]
            ),
            "tester",
        )
        provider_id = provider.id
        await session.rollback()

        relabelled = await secret_service.update_secret(
            provider_id, "api-key", IntegrationSecretUpdateRequest(description="labelled"), "editor"
        )
        assert relabelled.value == "issued"
        assert relabelled.description == "labelled"
        assert relabelled.updated_by == "editor"
        await session.rollback()

        rotated = await secret_service.update_secret(
            provider_id, "api-key", IntegrationSecretUpdateRequest(value="rotated"), "editor"
        )
        assert rotated.value == "rotated"
        await session.rollback()

        with pytest.raises(NotFoundError):
            await secret_service.update_secret(
                provider_id, "absent", IntegrationSecretUpdateRequest(value="v"), "editor"
            )
        await session.rollback()
        with pytest.raises(NotFoundError):
            await secret_service.update_secret(
                uuid4(), "api-key", IntegrationSecretUpdateRequest(value="v"), "editor"
            )
