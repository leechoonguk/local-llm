# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio
import secrets as random_secrets
from collections.abc import AsyncIterator, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from itertools import count
from time import perf_counter
from uuid import UUID

import httpx2
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    IntegrationConfigurationError,
    IntegrationError,
    IntegrationQuotaError,
)
from app.core.integration import (
    IntegrationClient,
    IntegrationExecutionResult,
    IntegrationPage,
    paging_family,
    paging_window,
)
from app.models.integration.operation import IntegrationOperation
from app.models.integration.secret import IntegrationSecret
from app.repositories.integration.call import IntegrationCallRepository
from app.repositories.integration.operation import IntegrationOperationRepository
from app.repositories.integration.secret import IntegrationSecretRepository
from app.schemas.integration.call import IntegrationCallCreateInternal


# ============================================================
# Constants
# ============================================================

#: Where this process starts its round-robin. Random per process, then
#: advancing per call: the scheduler and a manual run spread across the pool
#: instead of both wearing the first key first, without a row write per call.
_rotation_offset = count(random_secrets.randbelow(1 << 16))

logger = structlog.get_logger(__name__)


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
        self.secret_repository = IntegrationSecretRepository(session)
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

        **The key pool is invisible from here up.** A provider whose secrets
        share a `rotation_group` is one credential to the caller: each try
        sends the next member, and an answer carrying one of the operation's
        `quota_codes` sits that member out for the code's seconds and sends
        the same request with the next one. Every try is its own call log row (the
        log answers "which key hit the quota"). The caller sees the refusal
        only when every member is spent, and then as `IntegrationQuotaError`,
        which names the moment the first member comes back - the endpoint
        reports it, the walk sleeps until then.
        """
        self._last_call_id = None
        pool = await self.secret_repository.list_pool(provider_code, datetime.now(UTC))
        offset = next(_rotation_offset)
        tries = max((len(members) for members in pool.values()), default=1)
        attempt = 0
        # The last try is the one that lets a quota refusal through - there
        # is no member left to send it with - so the loop has no fall-through.
        while True:
            choice = {
                group: members[(offset + attempt) % len(members)] for group, members in pool.items()
            }
            integration_client = await IntegrationClient.from_database(
                session=self.session,
                provider_code=provider_code,
                operation_code=operation_code,
                client=client,
                secrets=choice,
            )
            try:
                result = await integration_client.execute(inputs)
            except IntegrationError as exc:
                sit_out = integration_client.operation.quota_codes.get(str(exc.envelope_value))
                if sit_out is None:
                    raise
                # Marked whether or not a member is left to try: a spent key
                # that the last try leaves unmarked is the first key the next
                # call sends - measured, the pool then refused twice a second.
                await self._mark_exhausted(choice.values(), timedelta(seconds=sit_out), actor)
                if attempt == tries - 1:
                    raise await self._quota_error(provider_code, exc, sit_out) from exc
                result = None
            finally:
                self._last_call_id = await self._create_call_log(integration_client, actor)
                await integration_client.aclose()
            if result is not None:
                return result, self._last_call_id
            attempt += 1

    async def walk_operation(
        self,
        provider_code: str,
        operation_code: str,
        *,
        actor: str,
        page_size: int,
        end_codes: frozenset[str],
    ) -> AsyncIterator[IntegrationPage]:
        """Read a paging operation from its first window to its last, one page per yield.

        One rule ends the walk, whatever the provider: **fewer records than
        the window asked for**. A window past the last record is that rule
        too — it holds zero rows — and the portal that answers such a window
        with a refusal instead of an empty page (`end_codes`) is read as the
        empty page it means. Nothing else is consulted: a `total_count` field
        is not trusted (measured fixed at `1` on some operations), and there
        is no cursor to keep, because the caller reads the whole feed.

        The family comes off the operation's own REQUEST fields, so the caller
        states a width and nothing about the wire.

        **A spent pool is a wait, not a failure.** When every key has answered
        a quota code the error names the moment the first comes back; the walk
        sleeps until then and asks for the same window again. A pass over a
        million-row feed spans several quota windows by design, and a run that
        failed at each would never reach the end.
        """
        # Its own transaction for the same reason as each call below: a read
        # left open here would be the idle transaction every window then holds.
        async with self.session.begin():
            operation = await self.get_operation(provider_code, operation_code)
            family = paging_family(
                field.key for field in operation.fields if field.direction == "REQUEST"
            )
        if family is None:
            raise IntegrationConfigurationError(
                f"{provider_code}/{operation_code} declares no paging family and cannot be walked"
            )
        index = 0
        while True:
            window = paging_window(family, index, page_size)
            started = perf_counter()
            try:
                # Each call is its own transaction: the configuration read
                # would otherwise stay open as one idle transaction per window.
                async with self.session.begin():
                    result, call_id = await self.execute_operation(
                        provider_code, operation_code, window, actor=actor
                    )
                payload = result.canonical_payload
                # An operation mapping absolute pointers hands back one record,
                # not a page; iterating it would hand the ledger its keys.
                records: list[object] = [payload] if isinstance(payload, Mapping) else list(payload)
            except IntegrationQuotaError as exc:
                wait = (exc.retry_at - datetime.now(UTC)).total_seconds()
                logger.info(
                    "integration.walk.quota_wait",
                    provider=provider_code,
                    operation=operation_code,
                    retry_at=exc.retry_at.isoformat(),
                )
                await asyncio.sleep(max(wait, 0))
                continue
            except IntegrationError as exc:
                if exc.envelope_value not in end_codes:
                    raise
                records = []
                call_id = self.last_call_id
            yield IntegrationPage(
                window=window,
                records=records,
                call_id=call_id,
                duration_ms=int((perf_counter() - started) * 1000),
            )
            if len(records) < page_size:
                return
            index += 1

    async def _quota_error(
        self, provider_code: str, refusal: IntegrationError, sit_out: int
    ) -> IntegrationQuotaError:
        """The refusal the pool's last member answered, with the moment to retry.

        The moment is the earliest `exhausted_until` of the pool, read after
        the marks were committed; a provider with no pool at all has nothing
        marked, and its single key comes back after the code's own window.
        """
        retry_at = await self.secret_repository.next_available_at(provider_code)
        if retry_at is None:
            retry_at = datetime.now(UTC) + timedelta(seconds=sit_out)
        return IntegrationQuotaError(
            refusal.provider,
            refusal.operation,
            refusal.detail,
            retry_at=retry_at,
            status_code=refusal.status_code,
            body=refusal.body,
            envelope_key=refusal.envelope_key,
            envelope_value=refusal.envelope_value,
        )

    async def _mark_exhausted(
        self, members: Iterable[IntegrationSecret], window: timedelta, actor: str
    ) -> None:
        """Sit the members of this try out for the window, on their own session.

        Own session for the reason `_create_call_log` gives: the caller's may
        be mid-transaction, and a mark that rolls back with the caller's
        failure would send the spent key again on the next try.
        """
        until = datetime.now(UTC) + window
        async with AsyncSession(self.session.bind, expire_on_commit=False) as session:
            secret_repository = IntegrationSecretRepository(session)
            async with session.begin():
                for member in members:
                    await secret_repository.mark_exhausted(member.id, until, actor)

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
