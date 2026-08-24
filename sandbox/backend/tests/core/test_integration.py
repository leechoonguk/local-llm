"""Transport behaviour of IntegrationClient: rendering, retries, and error mapping."""

from __future__ import annotations

import json
from datetime import date, datetime

import httpx2
import pytest
import structlog

from app.core.exceptions import (
    IntegrationConfigurationError,
    IntegrationError,
    IntegrationInputError,
    IntegrationRateLimitError,
    IntegrationTimeoutError,
)
from app.core.integration import IntegrationClient
from app.models.integration import (
    Integration,
    IntegrationField,
    IntegrationOperation,
    IntegrationSecret,
)


def request_field(**overrides) -> IntegrationField:
    """An outbound field. `key` is the caller-facing name, `wire_path` the wire name."""
    values = {
        "direction": "REQUEST",
        "location": "QUERY",
        "value_type": "STRING",
        "required": False,
    }
    values.update(overrides)
    return IntegrationField(**values)


def response_field(**overrides) -> IntegrationField:
    """An inbound body field read from `wire_path` (a JSON Pointer)."""
    values = {
        "direction": "RESPONSE",
        "location": "BODY",
        "value_type": "STRING",
        "required": False,
    }
    values.update(overrides)
    return IntegrationField(**values)


def response_header(**overrides) -> IntegrationField:
    """An inbound header rule; `wire_path` is the header name."""
    values = {
        "direction": "RESPONSE",
        "location": "HEADER",
        "value_type": "STRING",
        "required": False,
    }
    values.update(overrides)
    return IntegrationField(**values)


def secret(name: str = "api-key", value: str = "secret-value") -> IntegrationSecret:
    """An enabled secret, since a disabled one is a separate configuration case."""
    return IntegrationSecret(name=name, value=value, enabled=True)


def operation(**overrides) -> IntegrationOperation:
    """Build a minimal operation whose defaults keep the suite fast.

    The millisecond timeouts and 1ms backoff let the retry paths run for real
    instead of being mocked out.
    """
    provider = Integration(
        code="test",
        display_name="Test",
        base_url="https://example.com",
        enabled=True,
    )
    fields = list(overrides.pop("fields", []))
    values = {
        "code": "lookup",
        "method": "GET",
        "path_template": "/lookup",
        "request_media_type": None,
        "response_format": "JSON",
        "response_root": None,
        "connect_timeout_ms": 10,
        "read_timeout_ms": 50,
        "max_retries": 2,
        "retry_base_ms": 1,
        "retry_max_ms": 2,
        "idempotent": True,
        "request_schema": None,
        "enabled": True,
        "fields": fields,
    }
    values.update(overrides)
    return IntegrationOperation(provider=provider, **values)


def client(handler, **overrides) -> IntegrationClient:
    """Wrap an operation in a client whose transport is the given handler.

    Asserting inside the handler is how a test sees what left the process.
    """
    return IntegrationClient(
        operation=operation(**overrides),
        client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_execute_renders_request_and_normalizes_response() -> None:
    """One call exercises every field location in both directions.

    Path, query, header, body, secret-free literals and context values are all
    rendered from configuration, and the reply is reduced to caller-facing keys.
    The path value contains a slash, so a missing encode step shows up here as
    a wrong URL rather than at a provider.
    """
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.raw_path.startswith(b"/lookup/order%2F1")
        assert request.url.params["q"] == "summer"
        assert request.headers["accept"] == "application/json"
        assert request.headers["x-actor"] == "actor-1"
        assert json.loads(request.content) == {"payload": {"name": "tea"}}
        return httpx2.Response(
            200,
            headers={"X-Remaining": "3"},
            json={"data": {"orderId": "order-1", "name": "tea"}},
        )

    configured = client(
        handler,
        path_template="/lookup/{order_id}",
        method="POST",
        request_schema={
            "type": "object",
            "properties": {"payload": {"type": "object"}},
            "required": ["payload"],
        },
        fields=[
            request_field(
                key="order_id",
                location="PATH",
                wire_path="order_id",
                value_source="CALLER",
                value_type="STRING",
                required=True,
            ),
            request_field(
                key="q",
                location="QUERY",
                wire_path="q",
                value_source="CALLER",
                value_type="STRING",
                required=True,
            ),
            request_field(
                key="accept",
                location="HEADER",
                wire_path="accept",
                value_source="LITERAL",
                value="application/json",
                value_type="STRING",
                required=True,
            ),
            request_field(
                key="actor_id",
                location="HEADER",
                wire_path="x-actor",
                value_source="CONTEXT",
                value_type="STRING",
                required=True,
            ),
            request_field(
                key="name",
                location="BODY",
                wire_path="/payload/name",
                value_source="CALLER",
                value_type="STRING",
                required=True,
            ),
            response_header(
                wire_path="x-remaining",
                match_mode="ONE_OF",
                expected_values=["3", "4"],
                value_type="INTEGER",
                key="remaining",
            ),
            response_field(
                wire_path="/data/orderId",
                key="order_id",
                value_type="STRING",
                required=True,
            ),
            response_field(
                wire_path="/data/name",
                key="name",
                value_type="STRING",
                required=True,
                ordinal=1,
            ),
        ],
    )
    try:
        result = await configured.execute(
            {"order_id": "order/1", "q": "summer", "name": "tea"}, context={"actor_id": "actor-1"}
        )
    finally:
        await configured.aclose()

    assert result.canonical_payload == {"order_id": "order-1", "name": "tea"}
    assert result.metadata == {"remaining": 3}
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_execute_propagates_inbound_request_id() -> None:
    """The inbound request id travels outbound, so one trace spans both hops.

    Without it a provider-side incident cannot be tied to the request that
    caused it.
    """
    seen: dict[str, str] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["request_id"] = request.headers["x-request-id"]
        return httpx2.Response(200, json={})

    configured = client(handler)
    structlog.contextvars.bind_contextvars(request_id="req-123")
    try:
        await configured.execute({})
    finally:
        structlog.contextvars.clear_contextvars()
        await configured.aclose()
    assert seen == {"request_id": "req-123"}


@pytest.mark.asyncio
async def test_execute_uses_secret_and_caller_values() -> None:
    """A named secret resolves to its value and a caller input reaches the wire.

    The secret is asserted on the wire because a silently empty credential
    looks like a provider authorization bug. The caller value is asserted
    because a CALLER field has **no** default: what the caller sends is the only
    thing that can arrive.
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["x-api-key"] == "secret"
        assert request.url.params["limit"] == "10"
        return httpx2.Response(200, json={})

    configured = client(
        handler,
        fields=[
            request_field(
                key="api_key",
                location="HEADER",
                wire_path="x-api-key",
                value_source="SECRET",
                secret=secret("api-token", "secret"),
                value_type="STRING",
                required=True,
            ),
            request_field(
                key="limit",
                location="QUERY",
                wire_path="limit",
                value_source="CALLER",
                value=None,
                value_type="INTEGER",
                required=False,
            ),
        ],
    )
    try:
        await configured.execute({"limit": 10})
    finally:
        await configured.aclose()


@pytest.mark.asyncio
async def test_execute_retries_and_maps_errors() -> None:
    """Two 503s then a 200: the call succeeds and the attempt count is exact.

    Asserting the count is what catches a retry loop that runs more times than
    configured.
    """
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(503 if calls < 3 else 200, json={})

    configured = client(handler)
    try:
        result = await configured.execute({})
    finally:
        await configured.aclose()
    assert result.status_code == 200
    assert calls == 3


@pytest.mark.asyncio
async def test_execute_maps_timeout_network_and_rate_limit() -> None:
    """Each transport failure becomes its own domain error, with Retry-After kept.

    Retries are disabled so the mapping is observed rather than the recovery;
    collapsing these to one error would erase the client's status codes.
    """
    def timeout_handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("timeout", request=request)

    timeout_client = client(timeout_handler, max_retries=0)
    with pytest.raises(IntegrationTimeoutError):
        await timeout_client.execute({})
    await timeout_client.aclose()

    def network_handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("down", request=request)

    network_client = client(network_handler, max_retries=0)
    with pytest.raises(IntegrationError, match="unreachable"):
        await network_client.execute({})
    await network_client.aclose()

    def limit_handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(429, headers={"Retry-After": "0"}, json={})

    limit_client = client(limit_handler, max_retries=0)
    with pytest.raises(IntegrationRateLimitError) as exc_info:
        await limit_client.execute({})
    await limit_client.aclose()
    assert exc_info.value.retry_after == 0


@pytest.mark.asyncio
async def test_execute_rejects_invalid_configured_values() -> None:
    """A missing input and an unresolvable secret fail before any request.

    They raise different exceptions on purpose: one is the caller's fault, the
    other the configuration's, and they answer with different status codes.
    """
    configured = client(
        lambda request: httpx2.Response(200, json={}),
        path_template="/lookup/{id}",
        fields=[
            request_field(
                key="id",
                location="PATH",
                wire_path="id",
                value_source="CALLER",
                value_type="STRING",
                required=True,
            )
        ],
    )
    with pytest.raises(IntegrationInputError, match="Required input"):
        await configured.execute({})
    await configured.aclose()

    # A value the caller sent that cannot be rendered is the caller's mistake: it
    # answers 422 naming the input, not 500 for a ValueError escaping the serializer.
    unusable_input = client(
        lambda request: httpx2.Response(200, json={}),
        fields=[
            request_field(
                key="page_no",
                location="QUERY",
                wire_path="pageNo",
                value_source="CALLER",
                value_type="INTEGER",
                required=True,
            )
        ],
    )
    with pytest.raises(IntegrationInputError, match="Input is not a valid integer: page_no"):
        await unusable_input.execute({"page_no": "abc"})
    await unusable_input.aclose()

    # The same unrenderable value in a LITERAL row is the configuration's mistake.
    unusable_literal = client(
        lambda request: httpx2.Response(200, json={}),
        fields=[
            request_field(
                key="size",
                location="QUERY",
                wire_path="size",
                value_source="LITERAL",
                value="not-a-number",
                value_type="NUMBER",
                required=False,
            )
        ],
    )
    with pytest.raises(IntegrationConfigurationError, match="Value is not a number"):
        await unusable_literal.execute({})
    await unusable_literal.aclose()

    missing_secret = client(
        lambda request: httpx2.Response(200, json={}),
        fields=[
            request_field(
                key="api_key",
                location="HEADER",
                wire_path="x-api-key",
                value_source="SECRET",
                value_type="STRING",
                required=True,
            )
        ],
    )
    with pytest.raises(IntegrationConfigurationError, match="secret is unavailable"):
        await missing_secret.execute({})
    await missing_secret.aclose()

    # A required value the *configuration* owns is the configuration's fault, so
    # it answers with the configuration code even though the same branch decides
    # both: a caller cannot fix a LITERAL row with no value.
    missing_literal = client(
        lambda request: httpx2.Response(200, json={}),
        fields=[
            request_field(
                key="tenant",
                location="QUERY",
                wire_path="tenant",
                value_source="LITERAL",
                value=None,
                value_type="STRING",
                required=True,
            )
        ],
    )
    with pytest.raises(IntegrationConfigurationError, match="Required configured value"):
        await missing_literal.execute({})
    await missing_literal.aclose()


@pytest.mark.asyncio
async def test_execute_validates_response_headers_and_body() -> None:
    """A reply that does not match the configuration is refused, not passed on.

    Missing header, missing root, missing required field and a wrong type each
    fail here so a malformed provider payload never reaches a caller as data.
    """
    header_client = client(
        lambda request: httpx2.Response(200, json={}),
        fields=[
            response_header(
                wire_path="x-required", key="required_header", match_mode="PRESENT", required=True
            )
        ],
    )
    with pytest.raises(IntegrationError, match="Required response header"):
        await header_client.execute({})
    await header_client.aclose()

    # A root that resolves to a scalar is not a page: mapping needs elements to walk,
    # so a bare value is refused by name instead of silently mapping nothing.
    scalar_root = client(
        lambda request: httpx2.Response(200, json={"value": 1}),
        response_root="/value",
    )
    with pytest.raises(IntegrationError, match="not a page"):
        await scalar_root.execute({})
    await scalar_root.aclose()

    mapping_client = client(
        lambda request: httpx2.Response(200, json={}),
        fields=[
            response_field(
                wire_path="/missing", key="missing", value_type="STRING", required=True
            )
        ],
    )
    with pytest.raises(IntegrationError, match="Required response field"):
        await mapping_client.execute({})
    await mapping_client.aclose()

    # A provider value that contradicts the configured value_type is an upstream
    # failure (502), not a caller/configuration one (422).
    type_client = client(
        lambda request: httpx2.Response(200, json={"flag": "yes"}),
        fields=[
            response_field(wire_path="/flag", key="flag", value_type="BOOLEAN", required=True)
        ],
    )
    with pytest.raises(IntegrationError, match="does not match configured type"):
        await type_client.execute({})
    await type_client.aclose()


@pytest.mark.asyncio
async def test_execute_maps_every_record_on_a_page() -> None:
    """A mapped operation with a page root maps the rows over every element.

    Without this, describing a provider's columns cost the page: absolute pointers
    can only name one record (`/body/items/0/...`), so a 193-column provider had to
    choose between a described contract and more than one row per answer.
    """
    page_client = client(
        lambda request: httpx2.Response(
            200, json={"body": {"items": [{"NAME": "first"}, {"NAME": "second", "EXTRA": "x"}]}}
        ),
        response_root="/body/items",
        fields=[
            response_field(wire_path="/NAME", key="name", value_type="STRING", required=True),
            response_field(wire_path="/EXTRA", key="extra", value_type="STRING"),
        ],
    )
    result = await page_client.execute({})
    assert result.canonical_payload == [{"name": "first"}, {"name": "second", "extra": "x"}]
    await page_client.aclose()

    # An empty page is an answer, not a failure: no element means no row to check.
    empty_client = client(
        lambda request: httpx2.Response(200, json={"body": {"items": []}}),
        response_root="/body/items",
        fields=[response_field(wire_path="/NAME", key="name", value_type="STRING", required=True)],
    )
    assert (await empty_client.execute({})).canonical_payload == []
    await empty_client.aclose()

    # A required row still binds every element the page does carry.
    partial_client = client(
        lambda request: httpx2.Response(200, json={"body": {"items": [{"NAME": "a"}, {}]}}),
        response_root="/body/items",
        fields=[response_field(wire_path="/NAME", key="name", value_type="STRING", required=True)],
    )
    with pytest.raises(IntegrationError, match="Required response field"):
        await partial_client.execute({})
    await partial_client.aclose()

    # Past the last page this provider omits the collection entirely: a declared
    # page has an empty state, so nothing to map is an empty answer, not a 502.
    absent_client = client(
        lambda request: httpx2.Response(200, json={"body": {"totalCount": 6071}}),
        response_root="/body/items",
        fields=[response_field(wire_path="/NAME", key="name", value_type="STRING", required=True)],
    )
    assert (await absent_client.execute({})).canonical_payload == []
    await absent_client.aclose()

    # A root that names a record instead of a page is a configuration mistake the
    # mapping cannot paper over by mapping the record's own keys.
    record_root = client(
        lambda request: httpx2.Response(200, json={"body": {"items": {"NAME": "a"}}}),
        response_root="/body/items",
        fields=[response_field(wire_path="/NAME", key="name", value_type="STRING")],
    )
    with pytest.raises(IntegrationError, match="not a page"):
        await record_root.execute({})
    await record_root.aclose()


@pytest.mark.asyncio
async def test_from_database_and_client_lifecycle(factory) -> None:
    """A client built from stored rows runs, and only owns the client it created.

    Closing must not close the shared application client — that would break
    every later request in the process.
    """
    async with factory() as session:
        provider = Integration(
            code="stored",
            display_name="Stored",
            base_url="https://example.com",
            enabled=True,
        )
        provider.operations = [
            IntegrationOperation(
                code="ping",
                method="GET",
                path_template="/ping",
                connect_timeout_ms=10,
                read_timeout_ms=50,
                max_retries=0,
                retry_base_ms=1,
                retry_max_ms=1,
                idempotent=True,
                enabled=True,
            )
        ]
        session.add(provider)
        await session.commit()
        http_client = httpx2.AsyncClient(
            transport=httpx2.MockTransport(lambda request: httpx2.Response(200, json={}))
        )
        configured = await IntegrationClient.from_database(
            session=session,
            provider_code="stored",
            operation_code="ping",
            client=http_client,
        )
        assert (await configured.execute({})).status_code == 200
        await configured.aclose()
        assert not http_client.is_closed
        await http_client.aclose()
        with pytest.raises(IntegrationConfigurationError):
            await IntegrationClient.from_database(
                session=session, provider_code="stored", operation_code="missing"
            )

    owned = IntegrationClient(operation=operation())
    await owned.aclose()
    assert owned._client.is_closed


def test_serializers_pointers_and_retry_after() -> None:
    """Value conversion refuses guesses instead of sending a wrong wire value.

    `True` is not an integer and "yes" is not a boolean: coercing either would
    put a value on the wire the configuration never described.
    """
    assert IntegrationClient._serialize("1", "INTEGER", None) == 1
    assert IntegrationClient._serialize("1.5", "NUMBER", None) == 1.5
    assert IntegrationClient._serialize(True, "BOOLEAN", None) is True
    assert IntegrationClient._serialize(date(2026, 1, 2), "DATE", "%Y%m%d") == "20260102"
    serialized_datetime = IntegrationClient._serialize(
        datetime(2026, 1, 2, 3, 4), "DATETIME", None
    )
    assert str(serialized_datetime).startswith("2026")
    assert IntegrationClient._serialize({"x": 1}, "JSON", None) == {"x": 1}
    with pytest.raises(IntegrationConfigurationError):
        IntegrationClient._serialize(True, "INTEGER", None)
    with pytest.raises(IntegrationConfigurationError):
        IntegrationClient._serialize("yes", "BOOLEAN", None)
    with pytest.raises(IntegrationConfigurationError):
        IntegrationClient._serialize("today", "DATE", None)

    body: dict[str, object] = {}
    IntegrationClient._set_pointer(body, "/a/b", "value")
    assert IntegrationClient._get_pointer(body, "/a/b") == "value"
    assert IntegrationClient._get_pointer(["first"], "/0") == "first"
    assert IntegrationClient._get_pointer({}, "/missing") is None
    with pytest.raises(IntegrationConfigurationError):
        IntegrationClient._set_pointer({"a": "value"}, "/a/b", "other")

    assert IntegrationClient._convert_header("2", "INTEGER") == 2
    assert IntegrationClient._convert_header("2.5", "NUMBER") == 2.5
    assert isinstance(IntegrationClient._convert_header("0", "EPOCH_SECONDS"), str)
    assert isinstance(
        IntegrationClient._convert_header("Sun, 06 Nov 1994 08:49:37 GMT", "HTTP_DATE"), str
    )
    assert IntegrationClient._convert_header("3", "DURATION_SECONDS") == 3.0
    assert IntegrationClient._retry_after(httpx2.Response(429, headers={"Retry-After": "1"})) == 1
    assert (
        IntegrationClient._retry_after(httpx2.Response(429, headers={"Retry-After": "bad"})) is None
    )
    assert IntegrationClient._retry_after(httpx2.Response(429)) is None


@pytest.mark.asyncio
async def test_execute_retries_timeout_network_and_rate_limit() -> None:
    """A transient timeout, connection error or 429 recovers on the second try.

    The mapping test proves these become errors when retries are off; this one
    proves they are retried when they are on.
    """
    attempts = {"timeout": 0, "network": 0, "limit": 0}

    def timeout_handler(request: httpx2.Request) -> httpx2.Response:
        attempts["timeout"] += 1
        if attempts["timeout"] == 1:
            raise httpx2.ReadTimeout("timeout", request=request)
        return httpx2.Response(200, json={})

    def network_handler(request: httpx2.Request) -> httpx2.Response:
        attempts["network"] += 1
        if attempts["network"] == 1:
            raise httpx2.ConnectError("down", request=request)
        return httpx2.Response(200, json={})

    def limit_handler(request: httpx2.Request) -> httpx2.Response:
        attempts["limit"] += 1
        if attempts["limit"] == 1:
            return httpx2.Response(429, headers={"Retry-After": "0"}, json={})
        return httpx2.Response(200, json={})

    for key, handler in (
        ("timeout", timeout_handler),
        ("network", network_handler),
        ("limit", limit_handler),
    ):
        configured = client(handler)
        try:
            assert (await configured.execute({})).status_code == 200
        finally:
            await configured.aclose()
        assert attempts[key] == 2


@pytest.mark.asyncio
async def test_execute_handles_optional_disabled_and_invalid_responses() -> None:
    """A disabled field is inert and an optional one falls back to its default.

    Disabling is how an operation is changed without a migration, so a
    disabled row that still reaches the wire is a live configuration bug.
    """
    optional = client(
        lambda request: httpx2.Response(200, json={}),
        fields=[
            request_field(
                key="optional",
                location="QUERY",
                wire_path="optional",
                value_source="CALLER",
                value_type="STRING",
                required=False,
            ),
            request_field(
                key="ignored",
                location="QUERY",
                wire_path="ignored",
                value_source="LITERAL",
                value="ignored",
                value_type="STRING",
                required=True,
                enabled=False,
            ),
            response_header(wire_path="x-disabled", enabled=False),
            response_header(wire_path="x-optional"),
            response_field(
                wire_path="/missing",
                key="fallback",
                value_type="STRING",
                required=False,
                value="default",
            ),
            response_field(
                wire_path="/ignored",
                key="ignored",
                value_type="STRING",
                required=False,
                enabled=False,
            ),
        ],
    )
    try:
        assert (await optional.execute({})).canonical_payload == {"fallback": "default"}
    finally:
        await optional.aclose()

    unresolved = client(lambda request: httpx2.Response(200, json={}), path_template="/{missing}")
    with pytest.raises(IntegrationError, match="unresolved"):
        await unresolved.execute({})
    await unresolved.aclose()

    invalid_json = client(lambda request: httpx2.Response(200, content=b"not-json"))
    with pytest.raises(IntegrationError, match="not valid JSON"):
        await invalid_json.execute({})
    await invalid_json.aclose()

    header_mismatch = client(
        lambda request: httpx2.Response(200, headers={"x-mode": "no"}, json={}),
        fields=[
            response_header(
                wire_path="x-mode", match_mode="EXACT", expected_values=["yes"]
            )
        ],
    )
    with pytest.raises(IntegrationError, match="header validation"):
        await header_mismatch.execute({})
    await header_mismatch.aclose()


@pytest.mark.asyncio
async def test_backoff_and_error_status() -> None:
    """A 4xx surfaces the status, and a zero-delay backoff still completes.

    The caller needs the upstream status in the message to tell "provider
    refused" from "provider is down".
    """
    failed = client(lambda request: httpx2.Response(400, json={}), max_retries=0)
    with pytest.raises(IntegrationError, match="HTTP 400"):
        await failed.execute({})
    await failed._backoff(0, 0)
    await failed.aclose()


def test_remaining_runtime_helpers() -> None:
    """Pointer writes into an existing object, and the strict numeric refusal.

    These are the branches the larger cases never reach.
    """
    assert IntegrationClient._serialize("x", "STRING", None) == "x"
    with pytest.raises(IntegrationConfigurationError):
        IntegrationClient._serialize(True, "NUMBER", None)
    body: dict[str, object] = {"a": {}}
    IntegrationClient._set_pointer(body, "/a/b", "value")
    assert body == {"a": {"b": "value"}}
    assert IntegrationClient._convert_header("value", "STRING") == "value"


def test_integration_http_client_dependency_and_pointer_failure() -> None:
    """The dependency hands out the client on app state, never a new one.

    A per-request client would leak sockets and lose connection reuse. The
    pointer case covers an index past the end of a list.
    """
    from fastapi import FastAPI, Request

    from app.dependencies.integrations import get_integration_http_client

    app = FastAPI()
    http_client = httpx2.AsyncClient()
    app.state.integration_http_client = http_client
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "app": app})
    assert get_integration_http_client(request) is http_client
    assert IntegrationClient._get_pointer(["only"], "/1") is None


@pytest.mark.asyncio
async def test_execute_decodes_xml_response_format() -> None:
    """XML providers map to the same JSON Pointer shape as JSON providers."""
    xml_body = (
        "<response><header><resultCode>00</resultCode></header>"
        "<body><items>"
        "<item><FOOD_NM_KR>신라면</FOOD_NM_KR><AMT_NUM3>8.33</AMT_NUM3></item>"
        "<item><FOOD_NM_KR>진라면</FOOD_NM_KR><AMT_NUM3>7.10</AMT_NUM3></item>"
        "</items></body></response>"
    )

    configured = client(
        lambda request: httpx2.Response(200, text=xml_body),
        response_format="XML",
        fields=[
            response_field(
                wire_path="/body/items/item/0/FOOD_NM_KR",
                key="food_name",
                value_type="STRING",
                required=True,
            ),
            response_field(
                wire_path="/body/items/item/0/AMT_NUM3",
                key="protein_g",
                value_type="NUMBER",
                required=True,
                ordinal=1,
            ),
        ],
    )
    try:
        result = await configured.execute({})
    finally:
        await configured.aclose()

    assert result.canonical_payload == {"food_name": "신라면", "protein_g": 8.33}
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_execute_rejects_malformed_xml_response() -> None:
    """Unparseable XML is a provider error, not a traceback from the parser."""
    configured = client(
        lambda request: httpx2.Response(200, text="<response><unclosed>"),
        response_format="XML",
    )
    with pytest.raises(IntegrationError, match="not valid XML"):
        await configured.execute({})
    await configured.aclose()


def test_element_to_value_handles_empty_single_and_repeated_nodes() -> None:
    """Repeated tags become a list while a single tag stays scalar.

    That asymmetry is why XML pointers need this conversion: an empty node is
    None, and surrounding whitespace is not part of the value.
    """
    from xml.etree import ElementTree

    root = ElementTree.fromstring(
        "<root><empty/><single><a>1</a></single><spaced>  x  </spaced>"
        "<r>1</r><r>2</r><r>3</r></root>"
    )
    assert IntegrationClient._element_to_value(root) == {
        "empty": None,
        "single": {"a": "1"},
        "spaced": "x",
        "r": ["1", "2", "3"],
    }


@pytest.mark.asyncio
async def test_execute_rejects_body_that_violates_request_schema() -> None:
    """The rendered body is validated before it leaves the process."""
    configured = client(
        lambda request: httpx2.Response(200, json={}),
        method="POST",
        request_schema={"type": "object", "required": ["mandatory"]},
        fields=[
            request_field(
                key="optional",
                location="BODY",
                wire_path="/optional",
                value_source="LITERAL",
                value="present",
            )
        ],
    )
    with pytest.raises(IntegrationError, match="request does not match configured schema"):
        await configured.execute({})
    await configured.aclose()
