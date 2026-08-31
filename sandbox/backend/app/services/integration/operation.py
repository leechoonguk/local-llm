# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import IntegrationConfigurationError
from app.core.integration import IntegrationClient, IntegrationExecutionResult
from app.models.integration.operation import IntegrationOperation
from app.repositories.integration.operation import IntegrationOperationRepository


# ============================================================
# Classes
# ============================================================

class IntegrationOperationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.operation_repository = IntegrationOperationRepository(session)

    async def get_operation(self, provider_code: str, operation_code: str) -> IntegrationOperation:
        operation = await self.operation_repository.get_operation(provider_code, operation_code)
        if operation is None or not operation.provider.enabled or not operation.enabled:
            raise IntegrationConfigurationError("Integration operation is unavailable")
        return operation

    async def execute_operation(
        self,
        provider_code: str,
        operation_code: str,
        inputs: Mapping[str, object],
        *,
        client: httpx2.AsyncClient | None = None,
    ) -> IntegrationExecutionResult:
        """Execute a configured operation against the external API.

        Resolves the operation from the database and runs it through
        IntegrationClient — the only sanctioned outbound HTTP path. The
        caller-supplied inputs map to CALLER-sourced request fields.
        """
        integration_client = await IntegrationClient.from_database(
            session=self.session,
            provider_code=provider_code,
            operation_code=operation_code,
            client=client,
        )
        try:
            return await integration_client.execute(inputs)
        finally:
            await integration_client.aclose()
