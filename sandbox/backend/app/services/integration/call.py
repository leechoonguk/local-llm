# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.integration.call import IntegrationCall
from app.models.integration.provider import Integration
from app.repositories.integration.call import IntegrationCallRepository
from app.repositories.integration.provider import IntegrationProviderRepository


# ============================================================
# Classes
# ============================================================


class IntegrationCallService:
    """Reads one provider's call log — the evidence its configuration ever ran.

    The provider is loaded first so an unknown id answers 404 rather than an
    empty page that reads as "never called" (the same order
    `GET /batch/{id}/runs` uses for a schedule).

    The log is keyed on the provider's **code**, because that is what the row
    stores: `operation_id` is `SET NULL` and a `_replace_` revision re-inserts
    the operation, so a log joined on ids would lose exactly the history an
    incident asks about.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.provider_repository = IntegrationProviderRepository(session)
        self.call_repository = IntegrationCallRepository(session)

    async def list_provider_calls(
        self, integration_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[IntegrationCall]:
        provider = await self._provider(integration_id)
        return await self.call_repository.list_by_provider(provider.code, offset, limit)

    async def count_provider_calls(self, integration_id: UUID) -> int:
        provider = await self._provider(integration_id)
        return await self.call_repository.count_by_provider(provider.code)

    async def _provider(self, integration_id: UUID) -> Integration:
        provider = await self.provider_repository.get(integration_id)
        if provider is None:
            raise NotFoundError(integration_id)
        return provider
