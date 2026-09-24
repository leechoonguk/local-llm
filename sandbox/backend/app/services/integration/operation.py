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

    async def segment_total(
        self,
        provider_code: str,
        operation_code: str,
        segment: Mapping[str, object],
        *,
        actor: str,
    ) -> int:
        """How many records one coordinate of a feed holds - one window of one row.

        `execute_operation` reads the configuration on the caller's session and
        leaves that read open, which is why every caller of it owns a
        transaction (`_walk_windows` opens one per window). A caller that did
        not was measured 2026-09-16 07:02 KST: the segmented walk asked here for
        a year's `total_count`, the autobegun read stayed open, and the walk's
        own `begin()` raised "A transaction is already begun on this Session"
        before the portal was called at all. The transaction belongs with the
        read, so it lives here and not in the batch helper that asks.

        The count is the portal's own `total_count`, trusted for this one
        question and no other: it says whether a year holds anything, never how
        many windows to walk - a walk ends on a short page.
        """
        async with self.session.begin():
            result, _ = await self.execute_operation(
                provider_code,
                operation_code,
                {"range_start": 1, "range_end": 1, **segment},
                actor=actor,
            )
        return int(str(result.metadata.get("total_count") or 0))

    async def segmentation_of(
        self, provider_code: str, operation_code: str
    ) -> tuple[str, list[str]] | None:
        """The coordinate this operation is addressed by, or None for a flat feed.

        Which caller input splits a feed, and which values it takes, are facts
        about the service - the same kind as its window width and its quota
        codes, and they live where those live, on the operation row. A caller
        that walks a feed asks here rather than stating a coordinate of its own:
        a job that knew one portal's coordinate would be the only place that
        knew it, and every other job would carry the knowledge it does not use.

        The values are listed, never derived. Code that generated them would
        have to know what the coordinate *is* - that a 보고년도 counts upward and
        a region code does not - which is the knowledge this move took out of
        the walk.
        """
        async with self.session.begin():
            operation = await self.get_operation(provider_code, operation_code)
            segment_key = operation.segment_key
            segment_values = operation.segment_values
        # The column pair is constrained to be stated together; the check is what
        # makes that readable here rather than an assumption two files apart.
        if segment_key is None or segment_values is None:
            return None
        return segment_key, list(segment_values)

    async def walk_operation(
        self,
        provider_code: str,
        operation_code: str,
        *,
        actor: str,
        end_codes: frozenset[str],
        segment: Mapping[str, object] | None = None,
    ) -> AsyncIterator[IntegrationPage]:
        """Read a paging operation from its first window to its last, one page per yield.

        `segment` rides on every window of the walk. It is not a filter: a
        filter reads a subset and calls it the feed, while a segment is one
        coordinate of a feed that is walked over *every* value of it - 생산실적
        is published per 보고년도 and the years' counts sum to the whole
        (2026-09-15), so the years are how the feed is addressed, not which
        part of it is wanted. The positional walk inside one segment is
        unchanged, and so is the end rule.

        One rule ends the walk, whatever the provider: **fewer records than
        the window asked for**. A window past the last record is that rule
        too — it holds zero rows — and the portal that answers such a window
        with a refusal instead of an empty page (`end_codes`) is read as the
        empty page it means. Nothing else is consulted: a `total_count` field
        is not trusted (measured fixed at `1` on some operations), and there
        is no cursor to keep, because the caller reads the whole feed.

        The family comes off the operation's own REQUEST fields and the width off
        its `page_size`, so the caller states nothing about the wire. The width is
        the service's ceiling, not the job's: one gateway's narrowest service was
        making its widest walk five times the windows, and on a gateway whose
        windows cost more the deeper they are that was 13 hours against 66
        minutes (measured 2026-09-14).

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
            page_size = operation.page_size
            response_format = operation.response_format
            family = paging_family(
                field.key for field in operation.fields if field.direction == "REQUEST"
            )
        if response_format == "CSV":
            # A file is the whole feed in one answer: the walk is the file read
            # in chunks, and there is no family because there is no window.
            logger.info(
                "integration.walk.started",
                provider=provider_code,
                operation=operation_code,
                family="FILE",
                page_size=page_size,
            )
            async with httpx2.AsyncClient() as client:
                async for page in self._walk_file(
                    provider_code, operation_code, page_size, actor, client
                ):
                    yield page
            return
        if family is None:
            raise IntegrationConfigurationError(
                f"{provider_code}/{operation_code} declares no paging family and cannot be walked"
            )
        # The width this pass will actually ask for, said once at the start. It is
        # configuration read at run time, so a job that was started before a
        # migration changed it walks at the old width - and without this line the
        # only way to see which one was used is to join the step log to the call
        # log and read `numOfRows` out of a URL (measured 2026-09-14, twice).
        logger.info(
            "integration.walk.started",
            provider=provider_code,
            operation=operation_code,
            family=family,
            page_size=page_size,
        )
        # One HTTP client for the whole pass. Two reasons, both measured on the
        # screen provider: the session cookie lives on the client, so a client
        # per window fetched the bootstrap screen again every window (109 calls
        # became 218), and the host's minimum interval is only a rate when one
        # client paces every call of the pass.
        async with httpx2.AsyncClient() as client:
            async for page in self._walk_windows(
                provider_code,
                operation_code,
                family,
                page_size,
                end_codes,
                actor,
                client,
                segment or {},
            ):
                yield page

    async def _stream_operation(
        self,
        provider_code: str,
        operation_code: str,
        *,
        actor: str,
        client: httpx2.AsyncClient | None = None,
    ) -> AsyncIterator[list[dict[str, object]]]:
        """Read a file operation off the wire in chunks, and log the one call it made.

        `execute_operation` with the answer arriving in pieces: the same pool
        member choice, the same call log row written when the exchange is over -
        which for a file is after the last chunk, not after the status. There is
        no quota rotation here, because a file door states its refusals as HTTP
        429 (measured 2026-09-19: "busy key" and "today's ten are spent" both),
        which the client retries and then raises as `IntegrationRateLimitError`;
        a nightly pass downloads once, and a second key for a second download
        is not a case the ledger has.
        """
        self._last_call_id = None
        pool = await self.secret_repository.list_pool(provider_code, datetime.now(UTC))
        offset = next(_rotation_offset)
        choice = {group: members[offset % len(members)] for group, members in pool.items()}
        integration_client = await IntegrationClient.from_database(
            session=self.session,
            provider_code=provider_code,
            operation_code=operation_code,
            client=client,
            secrets=choice,
        )
        try:
            async for chunk in integration_client.stream({}):
                yield chunk
        finally:
            self._last_call_id = await self._create_call_log(integration_client, actor)
            await integration_client.aclose()

    async def _walk_file(
        self,
        provider_code: str,
        operation_code: str,
        page_size: int,
        actor: str,
        client: httpx2.AsyncClient,
    ) -> AsyncIterator[IntegrationPage]:
        """The chunks of one file, as the pages a ledger stage and a step log read.

        Each chunk is numbered as the row interval it holds, so the step log
        speaks the same rows a windowed walk's does. A step points at no call:
        the file is one exchange, and its log row is written when the last
        chunk has been read - after every step that could have pointed at it.
        The run's calls are still one query away, by operation and time.
        """
        index = 0
        started = perf_counter()
        # Its own transaction, as each window of a paged walk has: the
        # configuration read would otherwise stay open for the whole file.
        async with self.session.begin():
            async for chunk in self._stream_operation(
                provider_code, operation_code, actor=actor, client=client
            ):
                window: dict[str, object] = dict(paging_window("RANGE", index, page_size))
                yield IntegrationPage(
                    window=window,
                    records=list(chunk),
                    call_id=None,
                    duration_ms=int((perf_counter() - started) * 1000),
                )
                started = perf_counter()
                index += 1

    async def _walk_windows(
        self,
        provider_code: str,
        operation_code: str,
        family: str,
        page_size: int,
        end_codes: frozenset[str],
        actor: str,
        client: httpx2.AsyncClient,
        segment: Mapping[str, object],
    ) -> AsyncIterator[IntegrationPage]:
        """The windows of one walk, over a client the caller owns."""
        index = 0
        while True:
            window = paging_window(family, index, page_size) | dict(segment)
            started = perf_counter()
            try:
                # Each call is its own transaction: the configuration read
                # would otherwise stay open as one idle transaction per window.
                async with self.session.begin():
                    result, call_id = await self.execute_operation(
                        provider_code, operation_code, window, actor=actor, client=client
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
