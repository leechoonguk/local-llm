# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio
import random
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from time import perf_counter
from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree

import httpx2
import structlog
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
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
from app.repositories.integration.operation import IntegrationOperationRepository


# ============================================================
# Constants
# ============================================================

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
class _SentRequest:
    """What left the process, kept so the record can be written after the answer."""

    method: str
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

    method: str
    url: str
    request_headers: dict[str, str]
    request_body: object
    status_code: int | None
    response_headers: dict[str, str] | None
    response_body: str | None
    outcome: str
    duration_ms: int
    attempts: int
    request_id: str | None
    error_code: str | None
    error_detail: str | None


class IntegrationClient:
    """Execute one database-configured external HTTP operation."""


    @property
    def last_exchange(self) -> IntegrationExchange | None:
        """What the last `execute` sent and received, or None before the first call."""
        return self._exchange

    def __init__(
        self,
        *,
        operation: IntegrationOperation,
        client: httpx2.AsyncClient | None = None,
    ) -> None:
        self.operation = operation
        self.provider = operation.provider.code
        self._owns_client = client is None
        self._client = client or httpx2.AsyncClient()
        # The secret values this client has sent, so a failing provider's body can
        # be handed back without the credential it echoed. Per client, cleared at
        # the start of every execute.
        self._sent_secrets: set[str] = set()
        # The last exchange this client performed, for a caller that stores it.
        self._exchange: IntegrationExchange | None = None

    @classmethod
    async def from_database(
        cls,
        *,
        session: AsyncSession,
        provider_code: str,
        operation_code: str,
        client: httpx2.AsyncClient | None = None,
    ) -> IntegrationClient:
        operation = await IntegrationOperationRepository(session).get_operation(
            provider_code, operation_code
        )
        if operation is None or not operation.provider.enabled or not operation.enabled:
            raise IntegrationConfigurationError("Integration operation is unavailable")
        return cls(operation=operation, client=client)


    async def aclose(self) -> None:
        """Close a client owned by this integration instance."""
        if self._owns_client:
            await self._client.aclose()

    async def execute(
        self,
        inputs: Mapping[str, object],
        *,
        context: Mapping[str, object] | None = None,
    ) -> IntegrationExecutionResult:
        """Render, execute, validate, and normalize a configured operation."""
        self._sent_secrets.clear()
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
        # The whole call, not one attempt: a retried call took the time it took,
        # and the log is read to answer "why was that request slow".
        call_started = perf_counter()
        sent = _SentRequest(
            method=self.operation.method,
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
                response = await self._client.request(
                    self.operation.method,
                    url,
                    params=params,
                    json=body,
                    headers=headers,
                    timeout=timeout,
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
            if response.status_code == 429:
                retry_after = self._retry_after(response)
                if self.operation.idempotent and attempt < self.operation.max_retries:
                    await self._backoff(attempt, retry_after)
                    attempt += 1
                    continue
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
                attempt += 1
                continue
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

    def _record(
        self,
        sent: _SentRequest,
        started: float,
        attempt: int,
        outcome: str,
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
        """
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
                f"Input is not a valid {field.value_type.lower()}: {field.key}"
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
            if secret is None or secret.enabled is False:
                raise IntegrationConfigurationError(
                    f"Configured integration secret is unavailable: {field.key}"
                )
            value = secret.value
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
                raise IntegrationInputError(f"Required input is missing: {field.key}")
            raise IntegrationConfigurationError(
                f"Required configured value is missing: {field.key}"
            )
        return value

    @staticmethod
    def _serialize(value: object, value_type: str, format_value: str | None) -> object:
        """Render one value in the wire form its configured `value_type` declares.

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
        if self.operation.response_format == "XML":
            try:
                root = ElementTree.fromstring(response.text)
            except ElementTree.ParseError as exc:
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
            value = self._get_pointer(payload, field.wire_path)
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
            value = self._get_pointer(payload, field.wire_path)
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
        delay += random.uniform(0, delay * 0.1)
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
