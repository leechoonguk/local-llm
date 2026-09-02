# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import IntegrationConfigurationError
from app.core.integration import IntegrationClient, IntegrationExecutionResult
from app.models.integration.operation import IntegrationOperation
from app.repositories.integration.call import IntegrationCallRepository
from app.repositories.integration.operation import IntegrationOperationRepository
from app.schemas.integration.call import IntegrationCallCreateInternal


# ============================================================
# Classes
# ============================================================


class IntegrationOperationService:
    @property
    def last_call_id(self) -> UUID | None:
        """The call log row the last execution wrote, or None before the first.

        Held on the service for the same reason `IntegrationClient` holds its
        exchange: `execute_operation` raises six ways, and threading a second
        value through every one of them is how the failure path ends up
        without the id — which is the path a reader needs it on.
        """
        return self._last_call_id

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.operation_repository = IntegrationOperationRepository(session)
        self._last_call_id: UUID | None = None

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
        actor: str,
        client: httpx2.AsyncClient | None = None,
    ) -> tuple[IntegrationExecutionResult, UUID | None]:
        """Execute a configured operation, and say which call log row it wrote.

        The id travels with the result because the caller that records a batch
        step needs to point at the exchange: without it, "which request failed
        this window" is a timestamp search across a table two jobs write to.

        Resolves the operation from the database and runs it through
        IntegrationClient — the only sanctioned outbound HTTP path. The
        caller-supplied inputs map to CALLER-sourced request fields.

        Every attempt is logged to `integration_call`, success or failure, in
        the `finally`: a log written only on the happy path is missing exactly
        the calls anyone would open it for. This is the one place both callers
        pass through — the endpoint and the batch job — so neither can forget.
        """
        integration_client = await IntegrationClient.from_database(
            session=self.session,
            provider_code=provider_code,
            operation_code=operation_code,
            client=client,
        )
        self._last_call_id = None
        try:
            result = await integration_client.execute(inputs)
        finally:
            self._last_call_id = await self._create_call_log(integration_client, actor)
            await integration_client.aclose()
        return result, self._last_call_id

    async def _create_call_log(
        self, integration_client: IntegrationClient, actor: str
    ) -> UUID | None:
        """Store what the client last sent and received, on its own session.

        Not the caller's session, for two reasons measured here. It already
        holds the read that resolved the configuration, so `begin()` on it
        raises "a transaction is already begun". And a log that shares the
        caller's transaction disappears when that transaction rolls back —
        which is precisely the case it exists to explain.

        The engine comes from the caller's own session rather than from
        `core.database`: importing the module engine gave the process a second
        answer to "which database", and the API tests — which swap the session
        factory, not the module — silently wrote their audit rows to the real
        one.

        Deliberately unguarded: if this write fails while an integration error
        is in flight, the database error is raised *from* the provider's one,
        so the traceback still carries the verdict. Swallowing it would leave
        an incident with neither record.
        """
        exchange = integration_client.last_exchange
        if exchange is None:
            return None
        operation = integration_client.operation
        # expire_on_commit=False: the row's id is read after the commit, and an
        # expired instance would lazy-load there — under asyncio that is a
        # MissingGreenlet, not a query.
        async with AsyncSession(self.session.bind, expire_on_commit=False) as session:
            call_repository = IntegrationCallRepository(session)
            async with session.begin():
                call = await call_repository.create(
                    IntegrationCallCreateInternal.from_exchange(
                        exchange,
                        operation_id=operation.id,
                        provider_code=operation.provider.code,
                        operation_code=operation.code,
                        created_by=actor,
                    )
                )
            return call.id
