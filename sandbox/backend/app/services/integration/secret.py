# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.integration.secret import IntegrationSecret
from app.repositories.integration.provider import IntegrationProviderRepository
from app.repositories.integration.secret import IntegrationSecretRepository
from app.schemas.integration.secret import (
    IntegrationSecretCreateRequest,
    IntegrationSecretUpdateRequest,
)


# ============================================================
# Classes
# ============================================================

class IntegrationSecretService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.provider_repository = IntegrationProviderRepository(session)
        self.secret_repository = IntegrationSecretRepository(session)

    async def create_secret(
        self, integration_id: UUID, data: IntegrationSecretCreateRequest, created_by: str
    ) -> IntegrationSecret:
        async with self.session.begin():
            provider = await self.provider_repository.get(integration_id)
            if provider is None:
                raise NotFoundError(integration_id)
            if await self.secret_repository.get_secret(provider.id, data.name) is not None:
                raise ConflictError(f"Secret '{data.name}' already exists for this provider")
            return await self.secret_repository.create_secret(provider, data, created_by)

    async def update_secret(
        self,
        integration_id: UUID,
        name: str,
        data: IntegrationSecretUpdateRequest,
        updated_by: str,
    ) -> IntegrationSecret:
        """Rotate a credential in place; an absent `value` keeps the stored one."""
        async with self.session.begin():
            provider = await self.provider_repository.get(integration_id)
            if provider is None:
                raise NotFoundError(integration_id)
            secret = await self.secret_repository.get_secret(provider.id, name)
            if secret is None:
                raise NotFoundError(integration_id)
            return await self.secret_repository.update_secret(secret, data, updated_by)

    async def list_secrets(
        self, integration_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[IntegrationSecret]:
        provider = await self.provider_repository.get(integration_id)
        if provider is None:
            raise NotFoundError(integration_id)
        return await self.secret_repository.list_secrets(provider.id, offset, limit)

    async def delete_secret(self, integration_id: UUID, name: str) -> None:
        """Refuse to orphan a field: the secret FK is ON DELETE RESTRICT."""
        async with self.session.begin():
            provider = await self.provider_repository.get(integration_id)
            if provider is None:
                raise NotFoundError(integration_id)
            secret = await self.secret_repository.get_secret(provider.id, name)
            if secret is None:
                raise NotFoundError(integration_id)
            if await self.secret_repository.count_secret_references(secret.id) > 0:
                raise ConflictError(f"Secret '{name}' is still referenced by a request field")
            await self.secret_repository.delete_secret(secret)
