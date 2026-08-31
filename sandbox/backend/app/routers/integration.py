# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.core.settings import settings
from app.dependencies.auth import CurrentUserDep
from app.dependencies.integrations import IntegrationHttpClientDep
from app.dependencies.query import LimitQuery, OffsetQuery
from app.dependencies.services import (
    IntegrationOperationServiceDep,
    IntegrationProviderServiceDep,
    IntegrationSecretServiceDep,
)
from app.schemas.integration.operation import IntegrationExecuteRequest, IntegrationExecuteResponse
from app.schemas.integration.provider import (
    IntegrationCreateRequest,
    IntegrationReadResponse,
    IntegrationUpdateRequest,
    to_read,
    to_read_list,
)
from app.schemas.integration.secret import (
    IntegrationSecretCreateRequest,
    IntegrationSecretReadResponse,
    IntegrationSecretUpdateRequest,
)


# ============================================================
# Router
# ============================================================

router = APIRouter(
    prefix="/integration",
    tags=["integration"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_integration(
    data: IntegrationCreateRequest,
    integration_provider_service: IntegrationProviderServiceDep,
    current_user: CurrentUserDep,
) -> IntegrationReadResponse:
    return to_read(
        await integration_provider_service.create_integration(data, current_user.username)
    )


@router.get("/")
async def list_integrations(
    integration_provider_service: IntegrationProviderServiceDep,
    current_user: CurrentUserDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
) -> list[IntegrationReadResponse]:
    return to_read_list(await integration_provider_service.list_integrations(offset, limit))


@router.get("/{integration_id}")
async def get_integration(
    integration_id: UUID,
    integration_provider_service: IntegrationProviderServiceDep,
    current_user: CurrentUserDep,
) -> IntegrationReadResponse:
    return to_read(await integration_provider_service.get_integration(integration_id))


@router.patch("/{integration_id}")
async def update_integration(
    integration_id: UUID,
    data: IntegrationUpdateRequest,
    integration_provider_service: IntegrationProviderServiceDep,
    current_user: CurrentUserDep,
) -> IntegrationReadResponse:
    return to_read(
        await integration_provider_service.update_integration(
            integration_id, data, current_user.username
        )
    )


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: UUID,
    integration_provider_service: IntegrationProviderServiceDep,
    current_user: CurrentUserDep,
) -> dict[str, bool]:
    await integration_provider_service.delete_integration(integration_id)
    return {"ok": True}


@router.post("/{integration_id}/secrets", status_code=status.HTTP_201_CREATED)
async def create_integration_secret(
    integration_id: UUID,
    data: IntegrationSecretCreateRequest,
    integration_secret_service: IntegrationSecretServiceDep,
    current_user: CurrentUserDep,
) -> IntegrationSecretReadResponse:
    """Store a named provider credential. The value is never read back."""
    secret = await integration_secret_service.create_secret(
        integration_id, data, current_user.username
    )
    return IntegrationSecretReadResponse.model_validate(secret)


@router.get("/{integration_id}/secrets")
async def list_integration_secrets(
    integration_id: UUID,
    integration_secret_service: IntegrationSecretServiceDep,
    current_user: CurrentUserDep,
    offset: OffsetQuery = 0,
    limit: LimitQuery = settings.items_per_user,
) -> list[IntegrationSecretReadResponse]:
    secrets = await integration_secret_service.list_secrets(integration_id, offset, limit)
    return [IntegrationSecretReadResponse.model_validate(secret) for secret in secrets]


@router.put("/{integration_id}/secrets/{secret_name}")
async def update_integration_secret(
    integration_id: UUID,
    secret_name: str,
    data: IntegrationSecretUpdateRequest,
    integration_secret_service: IntegrationSecretServiceDep,
    current_user: CurrentUserDep,
) -> IntegrationSecretReadResponse:
    """Rotate or relabel a credential. An absent `value` keeps the stored one."""
    secret = await integration_secret_service.update_secret(
        integration_id, secret_name, data, current_user.username
    )
    return IntegrationSecretReadResponse.model_validate(secret)


@router.delete("/{integration_id}/secrets/{secret_name}")
async def delete_integration_secret(
    integration_id: UUID,
    secret_name: str,
    integration_secret_service: IntegrationSecretServiceDep,
    current_user: CurrentUserDep,
) -> dict[str, bool]:
    await integration_secret_service.delete_secret(integration_id, secret_name)
    return {"ok": True}


@router.post("/{integration_id}/operations/{operation_code}/execute")
async def execute_integration_operation(
    integration_id: UUID,
    operation_code: str,
    data: IntegrationExecuteRequest,
    integration_operation_service: IntegrationOperationServiceDep,
    integration_provider_service: IntegrationProviderServiceDep,
    integration_http_client: IntegrationHttpClientDep,
    current_user: CurrentUserDep,
) -> IntegrationExecuteResponse:
    """Execute one configured operation against the external API.

    Resolves the provider/operation from the database and runs it through the
    shared outbound HTTP client. `inputs` supplies CALLER-sourced request
    fields; SECRET values are resolved from the database, never the caller.
    """
    provider = await integration_provider_service.get_integration(integration_id)
    result = await integration_operation_service.execute_operation(
        provider.code,
        operation_code,
        data.inputs,
        client=integration_http_client,
    )
    return IntegrationExecuteResponse(
        canonical_payload=result.canonical_payload,
        metadata=result.metadata,
        status_code=result.status_code,
    )
