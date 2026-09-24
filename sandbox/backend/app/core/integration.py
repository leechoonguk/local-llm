# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio
import codecs
import csv
import random
import re
import zlib
from collections.abc import AsyncIterator, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from tempfile import SpooledTemporaryFile
from time import perf_counter
from typing import Any, Literal, cast, get_args
from urllib.parse import quote
from uuid import UUID
from xml.etree import ElementTree

import httpx2
import structlog
from defusedxml import ElementTree as DefusedElementTree
from defusedxml.common import DefusedXmlException
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from selectolax.parser import HTMLParser, Node
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    IntegrationConfigurationError,
    IntegrationError,
    IntegrationInputError,
    IntegrationRateLimitError,
    IntegrationTimeoutError,
)
from app.models.integration.field import IntegrationField
from app.models.integration.operation import IntegrationOperation
from app.models.integration.secret import IntegrationSecret
from app.repositories.integration.operation import IntegrationOperationRepository


# ============================================================
# Constants
# ============================================================
#: A caller sent the wrong shape, or sent nothing at all. Two codes because the
#: answer differs: fix the value, or supply it.
INPUT_TYPE_INVALID_CODE = "integration_input_type_invalid"

INPUT_REQUIRED_CODE = "integration_input_required"

logger = structlog.get_logger(__name__)

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# The canonical caller-facing paging inputs, by family. Wire names stay the
# provider's (`pageNo`/`numOfRows`, `startIdx`/`endIdx`); these are ours. An operation
# declares exactly one family or none: a position without a size — or two families at
# once — is not a window. RANGE arrived with I1250, which pages by row index and has
# no page number at all.
PAGING_FAMILIES: dict[str, frozenset[str]] = {
    "PAGE": frozenset({"page_no", "num_of_rows"}),
    "RANGE": frozenset({"range_start", "range_end"}),
}

PAGING_KEYS = frozenset(key for family in PAGING_FAMILIES.values() for key in family)

# How much of a failing provider's answer travels back to the caller. The whole
# point is that "the call failed" was unactionable, and the whole body is not the
# fix either: one XML page of this provider is 40KB, and an error payload nobody
# can read is the same defect with more bytes.
UPSTREAM_BODY_LIMIT = 2000

# What a recorded failure's detail may carry: the column is String(512), and a
# detail longer than a sentence is a body in the wrong field.
ERROR_DETAIL_LIMIT = 512

# A screen prints for people: the row a portal renders carries newlines and runs
# of spaces that mean nothing, and `총 213,690건` states a number with a comma in
# it. Both are normalised on the way in so a seeded locator reads what a reader
# sees, and an INTEGER column is not defeated by a thousands separator.
WHITESPACE_RUN = re.compile(r"\s+")


def _clean_text(text: str) -> str:
    """Collapse a rendered node's whitespace the way a browser displays it."""
    return WHITESPACE_RUN.sub(" ", text).strip()


# The request media types that travel as a form rather than a JSON body. A screen
# built for a browser reads exactly these two.
FORM_MEDIA_TYPES = frozenset({"multipart/form-data", "application/x-www-form-urlencoded"})

# The two bytes every gzip member starts with. A file door answers
# `application/gzip` on success and an XML refusal on failure (measured
# 2026-09-19: both `INFO-500` and `INFO-330` arrive as HTTP 429 with an XML
# body), so the body itself says whether to inflate it.
GZIP_MAGIC = b"\x1f\x8b"

# How a file's rows are read from the wire: bytes in pieces of this size, each
# inflated and decoded as it arrives. 2,046,504 rows are 448 MB of text, and a
# file read whole would be that much memory before the first row is staged.
FILE_READ_BYTES = 1 << 20

# How much of a downloaded file is held in memory before it spills to disk.
# The wire is drained before records are cut (see `_file_text`), so this is the
# whole compressed answer: 32 MB keeps every small feed in memory and spills
# the four that are bigger (I0300 124 MB, I0460 60 MB, C002 57 MB, I1420 42 MB).
FILE_SPOOL_BYTES = 32 << 20

# The transport's own loggers, named here beside the transport and held to
# WARNING by `configure_logging`: at INFO the client prints every request's
# full URL, and a provider's key travels in the URL (식품안전나라 in the path,
# data.go.kr as `serviceKey`) — measured 2026-09-08, 7,152 such lines in one
# night's stdout. `integration_response` and `integration_call` already record
# every exchange without the URL, so silencing the client loses nothing.
TRANSPORT_LOGGERS = (httpx2.__name__, "httpcore")


# ============================================================
# Classes
# ============================================================


@dataclass(frozen=True)
class IntegrationExecutionResult:
    # A record when the operation maps absolute pointers, a page when it maps every
    # element of `response_root` — a paging API's window comes back whole.
    canonical_payload: dict[str, object] | list[object]
    metadata: dict[str, object]
    status_code: int


@dataclass(frozen=True)
class IntegrationPage:
    """One window of a paging operation, as a feed walk hands it on.

    The window and the call log id ride with the records because the reader
    that stores a batch step needs all three and the walk is a generator: a
    bare list would leave the step without the window it was read for.
    """

    # The paging keys, plus any segment the walk carries (`report_year`), which
    # is why the values are not all integers.
    window: dict[str, object]
    records: list[object]
    call_id: UUID | None
    duration_ms: int


#: `ck_integration_call_method` — the verbs this client can issue.
CallMethod = Literal["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"]


#: `ck_integration_call_outcome` — how the exchange ended. `REFUSED` is the
#: provider answering no; the other three are it not answering at all.
CallOutcome = Literal["SUCCESS", "REFUSED", "TIMEOUT", "UNREACHABLE", "RATE_LIMITED"]


def paging_family(request_keys: Iterable[str]) -> str | None:
    """The paging family a set of REQUEST field keys declares, or None.

    Read off the fields rather than stated by a caller, so a job cannot name
    a family the operation does not take: the keys are the whole declaration,
    and a set that is not exactly one family is a configuration error the
    provider service refuses at write time. Takes the keys, not the
    operation, so the write-time check and the walk read the same thing off
    a request and off a row.
    """
    paging = set(request_keys) & PAGING_KEYS
    if not paging:
        return None
    family = next((name for name, keys in PAGING_FAMILIES.items() if paging == keys), None)
    if family is None:
        raise IntegrationConfigurationError(
            f"Paging inputs {sorted(paging)} are not one whole family — "
            f"declare exactly one of {sorted(PAGING_FAMILIES)}"
        )
    return family


def paging_window(family: str, index: int, size: int) -> dict[str, int]:
    """The caller inputs that ask for the `index`-th window (from 0) of `size` rows.

    Both families count from 1 on the wire: RANGE names the row interval
    (`1..1000`, `1001..2000`), PAGE names the page and its width.
    """
    if family == "RANGE":
        start = 1 + index * size
        return {"range_start": start, "range_end": start + size - 1}
    if family == "PAGE":
        return {"page_no": index + 1, "num_of_rows": size}
    raise IntegrationConfigurationError(f"Unknown paging family {family!r}")


def window_rows(window: Mapping[str, object]) -> tuple[int, int]:
    """The row interval a window of either family asks for, both ends inclusive.

    The batch step log speaks in rows whichever family the operation pages
    by, so a reader comparing two feeds' steps compares like with like. A
    segment riding on the window (`report_year`) is not a row bound and is
    not read here.
    """
    if "range_start" in window:
        return int(window["range_start"]), int(window["range_end"])  # type: ignore[arg-type]
    size = int(window["num_of_rows"])  # type: ignore[arg-type]
    start = (int(window["page_no"]) - 1) * size + 1  # type: ignore[arg-type]
    return start, start + size - 1


def _call_method(configured: str) -> CallMethod:
    """The verb a stored operation declares, proved against the log's vocabulary.

    `integration_operation.method` carries no check constraint while
    `integration_call.method` does, so a hand-edited row can hold a verb the log
    cannot store. Refusing here names the misconfigured operation; letting it
    through fails later as a constraint violation on the *log*, which reports
    the wrong table and hides which operation caused it.
    """
    if configured not in get_args(CallMethod):
        raise IntegrationConfigurationError(
            f"operation declares method {configured!r}, "
            f"not one of {', '.join(get_args(CallMethod))}"
        )
    return cast(CallMethod, configured)


@dataclass(frozen=True)
class _SentRequest:
    """What left the process, kept so the record can be written after the answer."""

    method: CallMethod
    url: str
    headers: dict[str, str]
    params: dict[str, str]
    body: object
    request_id: str | None


@dataclass(frozen=True)
class IntegrationExchange:
    """One executed call, as the caller may store it.

    The client owns the scrubbing because it is the only place that knows which
    secret values it resolved: the URL carries the credential as a path segment
    for these providers, so a raw URL in a log is the key in a log.
    """

    method: CallMethod
    url: str
    request_headers: dict[str, str]
    request_body: object
    status_code: int | None
    response_headers: dict[str, str] | None
    response_body: str | None
    outcome: CallOutcome
    duration_ms: int
    attempts: int
    request_id: str | None
    error_code: str | None
    error_detail: str | None
    secret_name: str | None


class _RecordCutter:
    """Cut a stream of text into RFC 4180 records, however the text is pieced.

    A record ends at a newline only when the quotes before it balance: a quoted
    field may carry a newline (450 of them in I0460, measured 2026-09-19), and
    the file arrives in 1 MB pieces that end wherever they end. `feed` hands
    back the records a piece completed, `finish` the one the file ended on.
    """

    def __init__(self) -> None:
        self._pending = ""
        self._record = ""

    def feed(self, text: str) -> list[str]:
        self._pending += text
        lines = self._pending.split("\n")
        self._pending = lines.pop()
        complete: list[str] = []
        for line in lines:
            self._record += line
            if self._record.count('"') % 2:
                self._record += "\n"
                continue
            complete.append(self._record.rstrip("\r"))
            self._record = ""
        return complete

    def finish(self) -> list[str]:
        rest = self._record + self._pending
        self._record = self._pending = ""
        return [rest.rstrip("\r")] if rest else []


class IntegrationClient:
    """Execute one database-configured external HTTP operation."""

    @property
    def last_exchange(self) -> IntegrationExchange | None:
        """What the last `execute` sent and received, or None before the first call."""
        return self._exchange

    @property
    def last_file_summary(self) -> dict[str, object] | None:
        """What the last `stream` read, as a caller that shows a download reports it."""
        return self._file_summary

    def __init__(
        self,
        *,
        operation: IntegrationOperation,
        client: httpx2.AsyncClient | None = None,
        secrets: Mapping[str, IntegrationSecret] | None = None,
    ) -> None:
        self.operation = operation
        self.provider = operation.provider.code
        self._owns_client = client is None
        self._client = client or httpx2.AsyncClient()
        # The pool member chosen for each rotation group, by group name. A field
        # bound to a grouped secret is sent with the chosen member; a field bound
        # to an ungrouped secret, or a group nobody chose for, sends its own.
        # The choice is the service's - it owns the session that remembers
        # which member is spent - so this client stays one request wide.
        self._secrets: Mapping[str, IntegrationSecret] = secrets or {}
        # The names of the secrets this execute sent, for the call log.
        self._secret_names: list[str] = []
        # The secret values this client has sent, so a failing provider's body can
        # be handed back without the credential it echoed. Per client, cleared at
        # the start of every execute.
        self._sent_secrets: set[str] = set()
        # When this client last sent a request, for a provider that has to be
        # paced. Per client, which is per pass: the interval is only a rate if
        # one client makes the calls (`IntegrationOperationService` hands its
        # walk one), and a client per call would pace nothing.
        self._last_sent: float | None = None
        # The last exchange this client performed, for a caller that stores it.
        self._exchange: IntegrationExchange | None = None
        # What the last `stream` downloaded - name, type, bytes, rows - for the
        # caller that shows a download rather than its rows.
        self._file_summary: dict[str, object] | None = None
        self._file_bytes = 0

    @classmethod
    async def from_database(
        cls,
        *,
        session: AsyncSession,
        provider_code: str,
        operation_code: str,
        client: httpx2.AsyncClient | None = None,
        secrets: Mapping[str, IntegrationSecret] | None = None,
    ) -> IntegrationClient:
        operation = await IntegrationOperationRepository(session).get_operation(
            provider_code, operation_code
        )
        if operation is None or not operation.provider.enabled or not operation.enabled:
            raise IntegrationConfigurationError("Integration operation is unavailable")
        return cls(operation=operation, client=client, secrets=secrets)

    async def aclose(self) -> None:
        """Close a client owned by this integration instance."""
        if self._owns_client:
            await self._client.aclose()

    async def execute(  # noqa: C901, PLR0912, PLR0915
        self,
        inputs: Mapping[str, object],
        *,
        context: Mapping[str, object] | None = None,
    ) -> IntegrationExecutionResult:
        """Render, execute, validate, and normalize a configured operation.

        One frame on purpose. The size is the retry loop's five endings — refused
        contract, 429, 5xx, timeout, unreachable — and each of them records the
        same attempt bookkeeping (`sent`, `call_started`, `attempt`, the
        response) before it raises. Split, that bookkeeping becomes six
        signatures threading the same four values, and the ending that forgets
        one is a silent hole in the call log.
        """
        if self.operation.response_format == "CSV":
            return await self._execute_file(inputs, context)
        self._sent_secrets.clear()
        self._secret_names.clear()
        self._exchange = None
        request_context = dict(context or {})
        request_id = structlog.contextvars.get_contextvars().get("request_id")
        if request_id is not None:
            request_context.setdefault("request_id", request_id)
        path, params, headers, body = self._render_request(inputs, request_context)
        if self.operation.request_schema is not None:
            self._validate_json(body, self.operation.request_schema, "request")
        if request_id is not None:
            headers["X-Request-ID"] = str(request_id)
        url = f"{self.operation.provider.base_url.rstrip('/')}/{path.lstrip('/')}"
        timeout = httpx2.Timeout(
            self.operation.read_timeout_ms / 1000,
            connect=self.operation.connect_timeout_ms / 1000,
        )
        await self._ensure_session(headers, timeout)
        await self._pace()
        # The whole call, not one attempt: a retried call took the time it took,
        # and the log is read to answer "why was that request slow".
        call_started = perf_counter()
        sent = _SentRequest(
            method=_call_method(self.operation.method),
            url=url,
            headers=headers,
            params=params,
            body=body,
            request_id=None if request_id is None else str(request_id),
        )

        attempt = 0
        # One re-bootstrap per call: an expired cookie is answered with a screen that
        # holds no rows, which the ENVELOPE row refuses, and the second refusal is
        # the portal's answer rather than the session's age.
        session_retried = False
        while True:
            started = perf_counter()
            try:
                response = await self._client.request(
                    self.operation.method,
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                    **self._body_kwargs(body),
                )
            except httpx2.TimeoutException as exc:
                self._log("integration_timeout", started, attempt, exc=exc)
                if self.operation.idempotent and attempt < self.operation.max_retries:
                    await self._backoff(attempt)
                    attempt += 1
                    continue
                self._record(sent, call_started, attempt, "TIMEOUT", None)
                raise IntegrationTimeoutError(
                    self.provider, self.operation.code, "External API timed out"
                ) from exc
            except httpx2.TransportError as exc:
                self._log("integration_network_error", started, attempt, exc=exc)
                if self.operation.idempotent and attempt < self.operation.max_retries:
                    await self._backoff(attempt)
                    attempt += 1
                    continue
                self._record(sent, call_started, attempt, "UNREACHABLE", None)
                raise IntegrationError(
                    self.provider, self.operation.code, "External API unreachable"
                ) from exc

            self._log("integration_response", started, attempt, status=response.status_code)
            if response.is_success:
                # One choke point for the mapping failures: the envelope refusal,
                # the unparseable body, the root that is not a page, the missing
                # required column. Each of them raises from a helper that was
                # handed the payload and not the response, and each of them is a
                # verdict about *this* answer - so the answer is attached here
                # instead of threading a response through six signatures.
                try:
                    result = self._normalize_response(response)
                except IntegrationError as exc:
                    if self.operation.provider.transport == "HTML_FORM" and not session_retried:
                        self._log(
                            "integration_session_refresh",
                            started,
                            attempt,
                            status=response.status_code,
                        )
                        session_retried = True
                        self._reset_session()
                        await self._ensure_session(headers, timeout)
                        continue
                    if exc.status_code is None:
                        exc.status_code = response.status_code
                        exc.body = self._upstream_body(response)
                    # HTTP said yes and the contract said no: the log calls that
                    # REFUSED, because "200" alone would hide it.
                    self._record(
                        sent,
                        call_started,
                        attempt,
                        "REFUSED",
                        response,
                        error_code="integration_error",
                        error_detail=exc.detail,
                    )
                    raise
                self._record(sent, call_started, attempt, "SUCCESS", response)
                return result
            # A refusal by status: retried when the operation allows it, else
            # recorded and raised as the exception its status names.
            await self._refuse_or_retry(response, sent, call_started, attempt)
            attempt += 1

    async def stream(  # noqa: C901, PLR0912, PLR0915
        self,
        inputs: Mapping[str, object],
        *,
        context: Mapping[str, object] | None = None,
    ) -> AsyncIterator[list[dict[str, object]]]:
        """Read a CSV operation's file from the wire in chunks of `page_size` records.

        The file door of a portal answers the whole feed in one request - measured
        on 식품안전나라 I0460 (2026-09-19): 2,046,504 rows, 62.8 MB of gzip, four
        seconds, where the paged API of the same feed needs 2,047 windows against
        a daily ceiling of ~500 calls a key and cannot finish. So the answer is
        never held whole: the bytes are inflated and decoded as they arrive, cut
        at record boundaries (a quoted field may carry a newline - 450 of them in
        that file), and every `page_size` records are mapped through the same
        RESPONSE rows a paged answer is and handed on.

        The request half is `execute`'s: same rendering, same retries before the
        first byte (a timeout, an unreachable host, a 429 - which is how this door
        states both "busy key" and "today's ten are spent" -, a 5xx), same call
        record. What differs is after the status: there is no envelope, because a
        file's refusal is its status, and there is no root, because the file is
        the page. A failure *after* the first chunk is not retried - the reader has
        already been handed records, and a second reading would hand them twice.
        """
        if self.operation.response_format != "CSV":
            raise IntegrationConfigurationError(
                f"{self.operation.code} is not a file operation: stream reads CSV only"
            )
        self._sent_secrets.clear()
        self._secret_names.clear()
        self._exchange = None
        request_context = dict(context or {})
        request_id = structlog.contextvars.get_contextvars().get("request_id")
        if request_id is not None:
            request_context.setdefault("request_id", request_id)
        path, params, headers, body = self._render_request(inputs, request_context)
        if request_id is not None:
            headers["X-Request-ID"] = str(request_id)
        url = f"{self.operation.provider.base_url.rstrip('/')}/{path.lstrip('/')}"
        timeout = httpx2.Timeout(
            self.operation.read_timeout_ms / 1000,
            connect=self.operation.connect_timeout_ms / 1000,
        )
        await self._pace()
        call_started = perf_counter()
        sent = _SentRequest(
            method=_call_method(self.operation.method),
            url=url,
            headers=headers,
            params=params,
            body=body,
            request_id=None if request_id is None else str(request_id),
        )
        attempt = 0
        while True:
            started = perf_counter()
            try:
                request = self._client.build_request(
                    self.operation.method, url, params=params, headers=headers, timeout=timeout
                )
                response = await self._client.send(request, stream=True)
            except httpx2.TimeoutException as exc:
                self._log("integration_timeout", started, attempt, exc=exc)
                if self.operation.idempotent and attempt < self.operation.max_retries:
                    await self._backoff(attempt)
                    attempt += 1
                    continue
                self._record(sent, call_started, attempt, "TIMEOUT", None)
                raise IntegrationTimeoutError(
                    self.provider, self.operation.code, "External API timed out"
                ) from exc
            except httpx2.TransportError as exc:
                self._log("integration_network_error", started, attempt, exc=exc)
                if self.operation.idempotent and attempt < self.operation.max_retries:
                    await self._backoff(attempt)
                    attempt += 1
                    continue
                self._record(sent, call_started, attempt, "UNREACHABLE", None)
                raise IntegrationError(
                    self.provider, self.operation.code, "External API unreachable"
                ) from exc
            self._log("integration_response", started, attempt, status=response.status_code)
            if response.is_success:
                break
            # A refusal is small (239 bytes of XML, measured) and is what the
            # log exists to keep; the file itself is never read into memory.
            await response.aread()
            await response.aclose()
            await self._refuse_or_retry(response, sent, call_started, attempt)
            attempt += 1
        received = 0
        try:
            async for chunk in self._file_records(response):
                received += len(chunk)
                yield chunk
        except httpx2.TimeoutException as exc:
            # A body that stopped arriving is a timeout, which the log's own
            # vocabulary has a word for; it is not an unreachable host.
            self._record(sent, call_started, attempt, "TIMEOUT", None)
            raise IntegrationTimeoutError(
                self.provider, self.operation.code, "External API file timed out"
            ) from exc
        except httpx2.TransportError as exc:
            # No status on either: the row's own rule is that an unanswered
            # call carries none (`ck_integration_call_answered`), and a body
            # that stopped halfway is not an answer. Passing the response here
            # wrote 200 beside UNREACHABLE and Postgres refused the log row,
            # which failed the pass for the logging, not for the feed (measured
            # 2026-09-20 on I1420, 126 s in).
            self._record(sent, call_started, attempt, "UNREACHABLE", None)
            raise IntegrationError(
                self.provider, self.operation.code, "External API file ended early"
            ) from exc
        except IntegrationError as exc:
            self._record(
                sent,
                call_started,
                attempt,
                "REFUSED",
                response,
                error_code="integration_error",
                error_detail=exc.detail,
            )
            raise
        finally:
            await response.aclose()
        self._file_summary = self._describe_file(response, received)
        self._record(sent, call_started, attempt, "SUCCESS", response)

    async def _execute_file(
        self, inputs: Mapping[str, object], context: Mapping[str, object] | None
    ) -> IntegrationExecutionResult:
        """`execute` on a file: read it through, hand back what was downloaded.

        Two million rows are not an answer to any caller of `execute` - not the
        endpoint an operator presses, not the contract test - so the result is
        the download: name, type, bytes and rows, and an empty page. The ledger
        that wants the rows reads `stream`.
        """
        async for _ in self.stream(inputs, context=context):
            pass
        summary = self._file_summary or {}
        status = summary.get("status_code")
        return IntegrationExecutionResult(
            [], dict(summary), status if isinstance(status, int) else 200
        )

    async def _file_records(
        self, response: httpx2.Response
    ) -> AsyncIterator[list[dict[str, object]]]:
        """Records off the wire, `page_size` at a time, mapped through the RESPONSE rows.

        The first record is the header, and every later one is read against it
        by name - the same names the RESPONSE rows point at (`/PRDTNM`).
        """
        cutter = _RecordCutter()
        header: list[str] | None = None
        batch: list[str] = []
        async for text in self._file_text(response):
            for record in cutter.feed(text):
                if header is None:
                    header = self._csv_row(record)
                    continue
                batch.append(record)
                if len(batch) >= self.operation.page_size:
                    yield self._map_records(header, batch)
                    batch = []
        for record in cutter.finish():
            if header is None:
                header = self._csv_row(record)
            else:
                batch.append(record)
        if header is None:
            raise IntegrationError(
                self.provider, self.operation.code, "External API file has no header"
            )
        if batch:
            yield self._map_records(header, batch)

    async def _file_text(self, response: httpx2.Response) -> AsyncIterator[str]:
        """The body as text, piece by piece: inflated when it is gzip, BOM dropped.

        **The wire is drained to a spooled file before a record is cut.** A
        reader that stages every 1,000 records into Postgres pauses between
        reads, and the portal's Apache closes a connection that idles: measured
        2026-09-20, 축산물 생산실적 (41.8 MB, 3.4 M records) died 126 s in while
        `execute` - which reads as fast as it can - took the same file whole in
        42 s. Taking the bytes at wire speed and cutting them afterwards makes
        the pass independent of how slow its consumer is. `SpooledTemporaryFile`
        keeps a small file in memory and spills a large one to disk, so a
        130 MB answer costs disk, not heap.
        """
        inflater: zlib._Decompress | None = None
        decoder = codecs.getincrementaldecoder("utf-8")()
        first = True
        self._file_bytes = 0
        with SpooledTemporaryFile(max_size=FILE_SPOOL_BYTES) as spool:
            async for data in response.aiter_bytes(FILE_READ_BYTES):
                self._file_bytes += len(data)
                spool.write(data)
            spool.seek(0)
            while True:
                data = spool.read(FILE_READ_BYTES)
                if not data:
                    break
                if first and data[: len(GZIP_MAGIC)] == GZIP_MAGIC:
                    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
                text = decoder.decode(inflater.decompress(data) if inflater else data)
                if first:
                    text = text.removeprefix("\ufeff")
                    first = False
                yield text
        yield decoder.decode(inflater.flush() if inflater else b"", final=True)

    @staticmethod
    def _csv_row(record: str) -> list[str]:
        return next(csv.reader([record]))

    def _map_records(self, header: list[str], records: list[str]) -> list[dict[str, object]]:
        """One chunk of raw records as canonical payloads."""
        mapped: list[dict[str, object]] = []
        width = len(header)
        for values in csv.reader(records):
            if len(values) != width:
                raise IntegrationError(
                    self.provider,
                    self.operation.code,
                    f"External API file row has {len(values)} columns, header has {width}",
                )
            mapped.append(self._validate_body_fields(dict(zip(header, values, strict=True))))
        return mapped

    def _describe_file(self, response: httpx2.Response, rows: int) -> dict[str, object]:
        """The download as a caller sees it: what the portal named it, how big, how many."""
        disposition = response.headers.get("content-disposition", "")
        match = re.search(r'filename="?([^";]+)"?', disposition)
        return {
            "file_name": match.group(1) if match else None,
            "content_type": response.headers.get("content-type"),
            "content_length": self._file_bytes,
            "row_count": rows,
            "status_code": response.status_code,
        }

    async def _refuse_or_retry(
        self, response: httpx2.Response, sent: _SentRequest, call_started: float, attempt: int
    ) -> None:
        """A non-2xx answer: back off and return when it may be retried, else record and raise.

        Shared by `execute` and `stream` - the endings after the status are the
        same three whichever way the body is read: a 429 (`Retry-After` honoured),
        a retryable 5xx, and everything else refused as its status.
        """
        if response.status_code == 429:
            retry_after = self._retry_after(response)
            if self.operation.idempotent and attempt < self.operation.max_retries:
                await self._backoff(attempt, retry_after)
                return
            # Recorded by value, then raised as its own class: a stored
            # instance would hide which exception this is (instance-raise.yml).
            self._record(
                sent,
                call_started,
                attempt,
                "RATE_LIMITED",
                response,
                error_code="integration_rate_limited",
                error_detail="External API rate limited",
            )
            raise IntegrationRateLimitError(
                self.provider,
                self.operation.code,
                "External API rate limited",
                retry_after=retry_after,
                status_code=response.status_code,
                body=self._upstream_body(response),
            )
        if (
            response.status_code in RETRYABLE_STATUS_CODES
            and self.operation.idempotent
            and attempt < self.operation.max_retries
        ):
            await self._backoff(attempt)
            return
        self._record(
            sent,
            call_started,
            attempt,
            "REFUSED",
            response,
            error_code="integration_error",
            error_detail=f"External API error: HTTP {response.status_code}",
        )
        raise IntegrationError(
            self.provider,
            self.operation.code,
            f"External API error: HTTP {response.status_code}",
            status_code=response.status_code,
            body=self._upstream_body(response),
        )

    def _body_kwargs(self, body: object) -> dict[str, Any]:
        """How the rendered body travels, which is `request_media_type` and nothing else.

        A form screen does not read JSON: measured 2026-09-13, `CFCCC01F01/getList`
        answers its error page for a JSON body and the list for the same values as
        `multipart/form-data`. httpx encodes a `files` mapping of `(None, value)`
        parts as exactly that form, with no file part.
        """
        media = self.operation.request_media_type
        if media not in FORM_MEDIA_TYPES or not isinstance(body, dict):
            return {"json": body}
        fields = {key: "" if value is None else str(value) for key, value in body.items()}
        if media == "multipart/form-data":
            return {"files": {key: (None, value) for key, value in fields.items()}}
        return {"data": fields}

    async def _ensure_session(self, headers: dict[str, str], timeout: httpx2.Timeout) -> None:
        """Fetch the screen that mints this portal's session cookie, once per client.

        Measured 2026-09-13 on impfood.mfds.go.kr: the list POST answers a 5 KB
        `<title>Error</title>` page with no cookie jar, and the search screen's own
        GET sets `elevisor_for_j2ee_uid` and `HOMESESSION`. The jar lives on the
        client, not in a table: a cookie that expires in minutes is not configuration,
        and a stored one is a stale row that fails tomorrow's run.
        """
        provider = self.operation.provider
        if provider.transport != "HTML_FORM" or provider.bootstrap_path is None:
            return
        bootstrap_url = f"{provider.base_url.rstrip('/')}/{provider.bootstrap_path.lstrip('/')}"
        # The portal reads the Referer as well as the cookie: the screen the form
        # belongs to is the one it was fetched from.
        headers.setdefault("Referer", bootstrap_url)
        if len(self._client.cookies.jar) > 0:
            return
        await self._client.get(bootstrap_url, headers=headers, timeout=timeout)

    async def _pace(self) -> None:
        """Wait out the provider's minimum interval between calls.

        Measured 2026-09-13 on impfood: 40 calls a second apart and 60 calls half
        a second apart were answered; at a quarter of a second the host stopped
        answering after 38 calls, and every connection - including the list
        screen the nightly job reads - was refused for the next ~15 minutes. So
        the interval is a property of the host, not of one operation, and it is
        enforced here rather than in a job, where the next job would forget it.
        """
        interval = self.operation.provider.min_interval_ms / 1000
        if interval <= 0:
            return
        if self._last_sent is not None:
            wait = interval - (perf_counter() - self._last_sent)
            if wait > 0:
                await asyncio.sleep(wait)
        self._last_sent = perf_counter()

    def _reset_session(self) -> None:
        """Drop the jar so the next call bootstraps again."""
        self._client.cookies.clear()

    def _record(
        self,
        sent: _SentRequest,
        started: float,
        attempt: int,
        outcome: CallOutcome,
        response: httpx2.Response | None,
        *,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        """Remember this exchange, scrubbed, for a caller that wants to store it.

        Held on the client rather than returned: `execute` already returns a result
        and raises six ways, and threading a second value through every one of them
        is how the log ends up missing exactly the failures it exists for.
        """
        query = "&".join(f"{key}={value}" for key, value in sent.params.items())
        self._exchange = IntegrationExchange(
            method=sent.method,
            url=self._scrub(sent.url if query == "" else f"{sent.url}?{query}"),
            request_headers={key: self._scrub(value) for key, value in sent.headers.items()},
            request_body=self._scrub_body(sent.body),
            status_code=None if response is None else response.status_code,
            response_headers=(
                None
                if response is None
                else {key: value for key, value in response.headers.items()}
            ),
            response_body=None if response is None else self._upstream_body(response),
            outcome=outcome,
            duration_ms=round((perf_counter() - started) * 1000),
            attempts=attempt + 1,
            request_id=sent.request_id,
            error_code=error_code,
            error_detail=None if error_detail is None else error_detail[:ERROR_DETAIL_LIMIT],
            secret_name=None if not self._secret_names else ",".join(self._secret_names),
        )

    def _scrub(self, text: str) -> str:
        for secret in self._sent_secrets:
            if secret:
                text = text.replace(secret, "***")
        return text

    def _scrub_body(self, body: object) -> object:
        """Scrub the rendered body, which may carry a SECRET field of its own."""
        if isinstance(body, dict):
            return {
                key: self._scrub(value) if isinstance(value, str) else value
                for key, value in body.items()
            }
        return self._scrub(body) if isinstance(body, str) else body

    def _upstream_body(self, response: httpx2.Response) -> str:
        """A failing provider's own answer, scrubbed and bounded.

        Scrubbed before truncation, not after: truncating first can cut a
        credential in half and hand back the front of it.

        A file that was read is not kept: what the record holds of a 62 MB
        download is its size. A file door's refusal is small and is kept, as
        every refusal is.
        """
        if self.operation.response_format == "CSV" and response.is_success:
            return f"<{response.headers.get('content-type')} {self._file_bytes} bytes>"
        return self._scrub(response.text)[:UPSTREAM_BODY_LIMIT]

    def _request_fields(self) -> list[IntegrationField]:
        return sorted(
            (
                field
                for field in self.operation.fields
                if field.direction == "REQUEST" and field.enabled is not False
            ),
            key=lambda item: item.ordinal or 0,
        )

    def _response_fields(self, location: str) -> list[IntegrationField]:
        return sorted(
            (
                field
                for field in self.operation.fields
                if field.direction == "RESPONSE"
                and field.location == location
                and field.enabled is not False
            ),
            key=lambda item: item.ordinal or 0,
        )

    def _render_request(
        self, inputs: Mapping[str, object], context: Mapping[str, object]
    ) -> tuple[str, dict[str, str], dict[str, str], object | None]:
        path = self.operation.path_template
        params: dict[str, str] = {}
        headers: dict[str, str] = {}
        body: dict[str, object] = {}
        filters: list[str] = []
        body_used = False
        for field in self._request_fields():
            value = self._resolve_value(field, inputs, context)
            if value is None:
                continue
            serialized = self._serialize_request_value(field, value)
            if field.location == "PATH":
                path = path.replace("{" + field.wire_path + "}", quote(str(serialized), safe=""))
            elif field.location == "PATH_QUERY":
                filters.append(f"{field.wire_path}={quote(str(serialized), safe='')}")
            elif field.location == "QUERY":
                params[field.wire_path] = str(serialized)
            elif field.location == "HEADER":
                headers[field.wire_path] = str(serialized)
            else:
                self._set_pointer(body, field.wire_path, serialized)
                body_used = True
        if "{" in path or "}" in path:
            raise IntegrationError(
                self.provider, self.operation.code, "Request path variables are unresolved"
            )
        if filters:
            # A query string the provider only reads as a path segment: sending it as
            # `?k=v` is accepted and silently unfiltered (measured), so the joined
            # expression is appended as one segment instead.
            path = f"{path.rstrip('/')}/{'&'.join(filters)}"
        return (
            path,
            params,
            headers,
            body if body_used or self.operation.request_schema is not None else None,
        )

    def _serialize_request_value(self, field: IntegrationField, value: object) -> object:
        """Render one outbound value, blaming whoever owns the value that failed.

        A `CALLER` field carries what the caller sent, so `page_no="abc"` is the
        caller's mistake and answers 422 `integration_input_invalid` naming the input.
        Measured: the unparsable case escaped as a bare `ValueError` and answered 500,
        which tells the caller the server broke over their own typo.
        """
        try:
            return self._serialize(value, field.value_type, field.format)
        except IntegrationConfigurationError:
            if field.value_source != "CALLER":
                raise
            raise IntegrationInputError(
                f"Input is not a valid {field.value_type.lower()}: {field.key}",
                INPUT_TYPE_INVALID_CODE,
            ) from None

    def _resolve_value(
        self,
        field: IntegrationField,
        inputs: Mapping[str, object],
        context: Mapping[str, object],
    ) -> object | None:
        if field.value_source == "CALLER":
            # No fallback to the field's own `value`: a caller field with a hidden
            # default is a second source of truth for the same parameter, and it
            # silently sends something the caller never asked for. An absent input
            # is absent — `_render_request` omits the field, so the provider's own
            # default applies, and a required field raises below.
            value = inputs.get(field.key)
        elif field.value_source == "LITERAL":
            value = field.value
        elif field.value_source == "SECRET":
            secret = field.secret
            if secret is not None and secret.rotation_group is not None:
                secret = self._secrets.get(secret.rotation_group, secret)
            if secret is None or secret.enabled is False:
                raise IntegrationConfigurationError(
                    f"Configured integration secret is unavailable: {field.key}"
                )
            value = secret.value
            self._secret_names.append(secret.name)
            # Remembered for one purpose: scrubbing it back out of a failing
            # provider's body before that body reaches the caller. The key travels
            # as a path segment, and providers echo their request.
            self._sent_secrets.add(str(secret.value))
        else:
            value = context.get(field.key)
        if value is None and field.required:
            # A caller field is the caller's obligation; anything else missing is
            # the configuration's. The status follows: 422 caller vs 422
            # configuration, never 502 — nothing upstream has been called yet.
            if field.value_source == "CALLER":
                raise IntegrationInputError(
                    f"Required input is missing: {field.key}", INPUT_REQUIRED_CODE
                )
            raise IntegrationConfigurationError(
                f"Required configured value is missing: {field.key}"
            )
        return value

    @staticmethod
    def _serialize(value: object, value_type: str, format_value: str | None) -> object:  # noqa: C901
        """Render one value in the wire form its configured `value_type` declares.

        The branches are the vocabulary of `value_type`, one per wire form, flat
        and exhaustive. Five one-line functions behind a dispatch table would be
        more code and would hide that the list is complete.

        A mismatch is a caller/configuration disagreement, not an upstream
        failure, so it raises the 422 core exception. The response direction
        wraps it into IntegrationError: there the value came from the provider.
        """
        if value_type == "STRING":
            return str(value)
        if value_type == "INTEGER":
            if isinstance(value, bool):
                raise IntegrationConfigurationError("Boolean is not an integer")
            try:
                return int(str(value))
            except ValueError:
                raise IntegrationConfigurationError(f"Value is not an integer: {value}") from None
        if value_type == "NUMBER":
            if isinstance(value, bool):
                raise IntegrationConfigurationError("Boolean is not a number")
            try:
                return float(str(value))
            except ValueError:
                raise IntegrationConfigurationError(f"Value is not a number: {value}") from None
        if value_type == "BOOLEAN":
            if not isinstance(value, bool):
                raise IntegrationConfigurationError("Value is not boolean")
            return value
        if value_type in {"DATE", "DATETIME"}:
            if not isinstance(value, (date, datetime)):
                raise IntegrationConfigurationError("Value is not a date or datetime")
            return value.strftime(format_value) if format_value is not None else value.isoformat()
        return value

    @staticmethod
    def _set_pointer(body: dict[str, object], pointer: str, value: object) -> None:
        parts = [
            part.replace("~1", "/").replace("~0", "~") for part in pointer.lstrip("/").split("/")
        ]
        target = body
        for part in parts[:-1]:
            existing = target.get(part)
            if existing is None:
                child: dict[str, object] = {}
                target[part] = child
                target = child
            elif isinstance(existing, dict):
                target = existing
            else:
                raise IntegrationConfigurationError("Body field pointers conflict")
        target[parts[-1]] = value

    def _decode_payload(self, response: httpx2.Response) -> object:
        """Decode the response body per the operation's configured format.

        XML providers are converted to the same nested dict shape JSON pointers
        address, so `integration_response_field.source_pointer` stays uniform
        across formats. Repeated sibling tags become lists.
        """
        if self.operation.response_format == "HTML":
            # A screen, not an API: the parse is the whole decoder, and the rows
            # are found by CSS afterwards. No schema and no envelope keys exist
            # here beyond what the seeded locators name.
            return HTMLParser(response.text)
        if self.operation.response_format == "XML":
            try:
                # `defusedxml`, not the stdlib parser: measured on this Python
                # (3.14.7), `xml.etree` expands internal entities — three levels
                # of the classic nesting turned 3 tokens into 300 characters, and
                # the growth is exponential in the depth a provider chooses. A
                # compromised or careless provider could answer with a body that
                # expands to gigabytes inside this process. External SYSTEM
                # entities were already refused, so file reads were never the
                # exposure; the memory bomb was.
                root = DefusedElementTree.fromstring(response.text)
            except (ElementTree.ParseError, DefusedXmlException) as exc:
                raise IntegrationError(
                    self.provider, self.operation.code, "External API response is not valid XML"
                ) from exc
            return self._element_to_value(root)
        try:
            return response.json()
        except ValueError as exc:
            raise IntegrationError(
                self.provider, self.operation.code, "External API response is not valid JSON"
            ) from exc

    def _read_field(self, payload: object, field: IntegrationField) -> object:
        """Read one RESPONSE row out of the decoded answer, by its locator kind.

        The four kinds are two decoders: `POINTER` addresses the nested value a
        JSON or XML body decodes to, and the other three address an HTML screen,
        which has no pointers to write.
        """
        if field.locator_kind == "POINTER":
            return self._get_pointer(payload, field.wire_path)
        if not isinstance(payload, HTMLParser | Node):
            raise IntegrationConfigurationError(
                f"Locator {field.locator_kind} needs an HTML response: {field.key}"
            )
        return self._read_html(payload, field)

    def _read_html(self, node: HTMLParser | Node, field: IntegrationField) -> object:
        text: str | None = None
        if field.locator_kind == "CSS":
            text = self._css_text(node, field.wire_path)
        elif field.locator_kind == "SECTION":
            heading, _, selector = field.wire_path.partition("|")
            scope = self._section(node, heading)
            text = None if scope is None else self._css_text(scope, selector)
        elif field.locator_kind == "LABEL":
            text = self._labelled_cell(node, field.wire_path)
        else:
            match = re.search(field.wire_path, _clean_text(node.text()))
            if match is not None:
                text = match.group(1) if match.lastindex else match.group(0)
        if text is None or text == "":
            # An empty cell is a cell the screen drew with nothing in it, which is
            # the same absence as a pointer that resolves to nothing — so the row's
            # `required` decides, in one place, for both decoders.
            return None
        if field.value_type not in {"INTEGER", "NUMBER"}:
            return text
        # A screen prints numbers for people: `총 213,690건`. The envelope row that
        # carries a total is read straight by the walker, and nothing downstream
        # converts it, so the thousands separator is dropped and the type applied
        # here rather than left as text that only looks like a number.
        try:
            return self._serialize(text.replace(",", ""), field.value_type, None)
        except IntegrationConfigurationError as exc:
            raise IntegrationError(
                self.provider,
                self.operation.code,
                f"External API response field does not match configured type: {field.key}",
            ) from exc

    @staticmethod
    def _css_text(node: HTMLParser | Node, wire_path: str) -> str | None:
        """One selector's reading: the first match's text, an attribute, or every match.

        Three forms, each measured on a real screen:

        - `td:nth-child(3)` - the first match's text;
        - `a@href` - that match's attribute, because a list screen keeps a record's
          identity in its link and nowhere a reader can see;
        - `td:nth-child(2)[]` - every match, newline-joined, because a screen
          repeats a value down a column (원재료 한글명, one `td` per ingredient) and
          the ledger keeps a published list as the wire prints it. The split into
          rows is a derived table's job (rule://backend-ledger).
        """
        if wire_path.endswith("[]"):
            joined = "\n".join(_clean_text(one.text()) for one in node.css(wire_path[:-2]))
            return joined or None
        selector, _, attribute = wire_path.partition("@")
        found = node.css_first(selector)
        if found is None:
            return None
        if attribute:
            return found.attributes.get(attribute)
        return _clean_text(found.text())

    @staticmethod
    def _section(node: HTMLParser | Node, heading: str) -> Node | None:
        """The block a heading introduces: the first following sibling holding a table.

        A detail screen states several repeating groups (원재료 정보, 세부품목(유형)
        정보, 회수판매중지 정보) in tables that share one class and sit in anonymous
        divs, so a positional selector picks a different group per record kind -
        measured 2026-09-13, the set of tables differs between 가공식품 and 축산물.
        What is stable is the `h3` above each group, and that is the only anchor the
        screen offers. The heading is matched on its text, and the block is the first
        sibling after it that contains a table.
        """
        for candidate in node.css("h1, h2, h3, h4, h5, h6"):
            if _clean_text(candidate.text()) != heading:
                continue
            node_at = candidate
            while node_at is not None:
                sibling = node_at.next
                while sibling is not None:
                    if sibling.tag == "table" or sibling.css_first("table") is not None:
                        return sibling
                    sibling = sibling.next
                node_at = node_at.parent
        return None

    @staticmethod
    def _labelled_cell(node: HTMLParser | Node, label: str) -> str | None:
        """The `td` beside the `th` that reads `label`.

        Measured 2026-09-13 on `CFCCC01F03`: a record carrying 부적합 or 회수 blocks
        shifts every later header, so a positional locator reads a neighbouring
        field's value and calls it this one's.
        """
        for header in node.css("th"):
            if _clean_text(header.text()) != label:
                continue
            sibling = header.next
            while sibling is not None and sibling.tag != "td":
                sibling = sibling.next
            if sibling is not None:
                return _clean_text(sibling.text())
        return None

    def _check_envelope(self, payload: object) -> dict[str, object]:
        """Enforce the wrapper's own verdict, and carry the rest of it as metadata.

        A provider that answers HTTP 200 for every outcome states the real one in its
        body wrapper. ENVELOPE rows are the contract for that wrapper: a row with a
        `match_mode` is checked and refuses the answer when it does not hold, and a row
        without one is carried into metadata — which is where a paged caller finds the
        total it needs to walk the window.

        Measured on I1250: an invalid key answers 200 with `RESULT.CODE INFO-100` and
        no rows, exactly like "no data" (INFO-200). Without this the two are the same
        empty page, and an expired credential looks like a quiet Tuesday.
        """
        collected: dict[str, object] = {}
        for field in self._response_fields("ENVELOPE"):
            value = self._read_field(payload, field)
            if field.match_mode is None or field.match_mode == "IGNORE":
                if value is not None:
                    collected[field.key] = value
                continue
            if not self._envelope_holds(field, value):
                raise IntegrationError(
                    self.provider,
                    self.operation.code,
                    f"External API refused the request: {field.key}={value} "
                    f"(expected {self._expected_label(field)})",
                    envelope_key=field.key,
                    envelope_value=None if value is None else str(value),
                )
            collected[field.key] = value
        return collected

    @staticmethod
    def _envelope_holds(field: IntegrationField, value: object) -> bool:
        if value is None:
            return False
        if field.match_mode == "PRESENT":
            return True
        expected = field.expected_values or []
        if field.match_mode == "EXACT":
            return len(expected) == 1 and str(value) == str(expected[0])
        return any(str(value) == str(candidate) for candidate in expected)

    @staticmethod
    def _expected_label(field: IntegrationField) -> str:
        if field.match_mode == "PRESENT":
            return "any value"
        return ", ".join(str(candidate) for candidate in field.expected_values or [])

    @classmethod
    def _element_to_value(cls, element: ElementTree.Element) -> object:
        children = list(element)
        if not children:
            text = element.text
            return text.strip() if text is not None else None
        mapped: dict[str, object] = {}
        for child in children:
            value = cls._element_to_value(child)
            existing = mapped.get(child.tag)
            if existing is None and child.tag not in mapped:
                mapped[child.tag] = value
            elif isinstance(existing, list):
                existing.append(value)
            else:
                mapped[child.tag] = [existing, value]
        return mapped

    def _normalize_response(self, response: httpx2.Response) -> IntegrationExecutionResult:
        """Validate the response, then build the canonical payload from the rows.

        `response_root` is the whole decision:

        - absent — the rows carry absolute pointers and produce one record;
        - present — the node it names is a page, and the rows are resolved against
          each element, so one row per provider column maps every record. This is the
          paging pattern: the caller's window arrives whole, and every column keeps
          the key, type and description the configuration gave it.
        """
        metadata = self._extract_headers(response)
        payload = self._decode_payload(response)
        metadata.update(self._check_envelope(payload))
        root_pointer = self.operation.response_root
        if root_pointer is None:
            return IntegrationExecutionResult(
                self._validate_body_fields(payload), metadata, response.status_code
            )
        if isinstance(payload, HTMLParser):
            # The root is the row selector, and its empty state is a screen that
            # drew the table with no rows in it — the same "past the last page"
            # a JSON provider states by dropping its items key.
            rows = payload.css(root_pointer)
            return IntegrationExecutionResult(
                [self._validate_body_fields(row) for row in rows],
                metadata,
                response.status_code,
            )
        page = self._get_pointer(payload, root_pointer)
        if page is None:
            # Measured: past the last page this provider answers `resultCode 00` with
            # `totalCount` intact and no `items` key at all. A declared page has an
            # empty state, so calling that a 502 blames the provider for "no rows".
            page = []
        if not isinstance(page, list):
            raise IntegrationError(
                self.provider,
                self.operation.code,
                f"Response root is not a page: {root_pointer}",
            )
        return IntegrationExecutionResult(
            [self._validate_body_fields(record) for record in page],
            metadata,
            response.status_code,
        )

    def _validate_body_fields(self, payload: object) -> dict[str, object]:
        """Enforce the configured body contract and return the mapped payload.

        `payload` is the whole response for absolute pointers, or one page element
        when the operation maps a page — the rows do not change, only what they are
        resolved against.
        """
        canonical_payload: dict[str, object] = {}
        for field in self._response_fields("BODY"):
            value = self._read_field(payload, field)
            if value is None:
                value = field.value
            if value is None and field.required:
                raise IntegrationError(
                    self.provider,
                    self.operation.code,
                    f"Required response field is missing: {field.key}",
                )
            if value is not None:
                # A type mismatch here came from the provider, not the caller:
                # re-blame it as an upstream failure (502) instead of a 422.
                try:
                    canonical_payload[field.key] = self._serialize(value, field.value_type, None)
                except IntegrationConfigurationError as exc:
                    raise IntegrationError(
                        self.provider,
                        self.operation.code,
                        f"External API response field does not match configured type: {field.key}",
                    ) from exc
        return canonical_payload

    def _extract_headers(self, response: httpx2.Response) -> dict[str, object]:
        metadata: dict[str, object] = {}
        for rule in self._response_fields("HEADER"):
            value = response.headers.get(rule.wire_path)
            if value is None and (rule.required or rule.match_mode == "PRESENT"):
                raise IntegrationError(
                    self.provider,
                    self.operation.code,
                    f"Required response header is missing: {rule.wire_path}",
                )
            if value is None:
                continue
            expected = rule.expected_values or []
            if (rule.match_mode == "EXACT" and value != expected[0]) or (
                rule.match_mode == "ONE_OF" and value not in expected
            ):
                raise IntegrationError(
                    self.provider,
                    self.operation.code,
                    f"Response header validation failed: {rule.wire_path}",
                )
            metadata[rule.key] = self._convert_header(value, rule.value_type)
        return metadata

    @staticmethod
    def _convert_header(value: str, value_type: str) -> object:
        if value_type == "INTEGER":
            return int(value)
        if value_type == "NUMBER":
            return float(value)
        if value_type == "EPOCH_SECONDS":
            return datetime.fromtimestamp(int(value)).isoformat()
        if value_type == "HTTP_DATE":
            return parsedate_to_datetime(value).isoformat()
        if value_type == "DURATION_SECONDS":
            return float(value)
        return value

    @staticmethod
    def _get_pointer(payload: object, pointer: str) -> object | None:
        value = payload
        for part in pointer.lstrip("/").split("/"):
            token = part.replace("~1", "/").replace("~0", "~")
            if isinstance(value, dict):
                value = value.get(token)
            elif isinstance(value, list) and token.isdigit() and int(token) < len(value):
                value = value[int(token)]
            else:
                return None
        return value

    def _validate_json(self, value: object, schema: dict[str, Any], direction: str) -> None:
        try:
            Draft202012Validator(schema).validate(value)
        except ValidationError as exc:
            raise IntegrationError(
                self.provider,
                self.operation.code,
                f"External API {direction} does not match configured schema: {exc.message}",
            ) from exc

    async def _backoff(self, attempt: int, retry_after: float | None = None) -> None:
        if retry_after is not None:
            delay = min(retry_after, self.operation.retry_max_ms / 1000)
        else:
            delay = min(
                self.operation.retry_base_ms / 1000 * (2**attempt),
                self.operation.retry_max_ms / 1000,
            )
        # Jitter, not a key: `random` spreads retries of concurrent callers so
        # they stop arriving in lockstep. Nothing here is a secret, so the cost
        # of `secrets` (a syscall per retry) buys nothing.
        delay += random.uniform(0, delay * 0.1)  # noqa: S311
        await asyncio.sleep(delay)

    @staticmethod
    def _retry_after(response: httpx2.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _log(
        self,
        event: str,
        started: float,
        attempt: int,
        *,
        status: int | None = None,
        exc: BaseException | None = None,
    ) -> None:
        log = logger.bind(
            provider=self.provider,
            operation=self.operation.code,
            attempt=attempt,
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
        if status is not None:
            log = log.bind(status_code=status)
        if exc is not None:
            log.warning(event, error=str(exc))
        else:
            log.info(event)
