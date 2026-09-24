"""IntegrationClient.stream: a CSV operation read off the wire in chunks."""

from __future__ import annotations

import gzip
from collections.abc import AsyncIterator

import httpx2
import pytest
import structlog

from app.core.exceptions import (
    IntegrationConfigurationError,
    IntegrationError,
    IntegrationRateLimitError,
    IntegrationTimeoutError,
)
from app.core.integration import _RecordCutter
from tests.core.test_integration import client, response_field


CSV = '\ufeffA,B\r\n1,x\r\n2,"two\nlines"\r\n3,z\r\n'

FILE_HEADERS = {
    "content-type": "application/gzip",
    "content-disposition": 'attachment; filename="I0460.csv.gz"',
}


def _file(**overrides):
    fields = [
        response_field(key="a", wire_path="/A", value_type="INTEGER"),
        response_field(key="b", wire_path="/B"),
    ]
    values = {"response_format": "CSV", "page_size": 2, "fields": fields, "path_template": "/file"}
    values.update(overrides)
    return values


async def _rows(configured, inputs=None):
    chunks = [chunk async for chunk in configured.stream(inputs or {})]
    return chunks


@pytest.mark.asyncio
async def test_stream_inflates_cuts_and_chunks_a_file() -> None:
    """Gzip in, records out: a BOM dropped, a quoted newline kept, page_size a chunk."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/file"
        return httpx2.Response(200, content=gzip.compress(CSV.encode()), headers=FILE_HEADERS)

    configured = client(handler, **_file())
    chunks = await _rows(configured)
    assert chunks == [
        [{"a": 1, "b": "x"}, {"a": 2, "b": "two\nlines"}],
        [{"a": 3, "b": "z"}],
    ]
    assert configured.last_file_summary == {
        "file_name": "I0460.csv.gz",
        "content_type": "application/gzip",
        "content_length": len(gzip.compress(CSV.encode())),
        "row_count": 3,
        "status_code": 200,
    }
    assert configured.last_exchange is not None
    assert configured.last_exchange.outcome == "SUCCESS"
    size = len(gzip.compress(CSV.encode()))
    assert configured.last_exchange.response_body == f"<application/gzip {size} bytes>"


@pytest.mark.asyncio
async def test_stream_reads_a_plain_file_too() -> None:
    """A body that is not gzip is read as it is: the magic bytes decide, not the header."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=CSV.encode(), headers={"content-type": "text/csv"})

    configured = client(handler, **_file(page_size=10))
    assert await _rows(configured) == [
        [{"a": 1, "b": "x"}, {"a": 2, "b": "two\nlines"}, {"a": 3, "b": "z"}]
    ]
    assert configured.last_file_summary is not None
    assert configured.last_file_summary["file_name"] is None


@pytest.mark.asyncio
async def test_execute_on_a_file_answers_the_download() -> None:
    """Two million rows are not an answer: execute hands back what was downloaded."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=gzip.compress(CSV.encode()), headers=FILE_HEADERS)

    result = await client(handler, **_file()).execute({})
    assert result.canonical_payload == []
    assert result.metadata["row_count"] == 3
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_stream_refuses_a_file_without_a_header_and_a_ragged_row() -> None:
    """An empty body and a row wider than its header are the file's own defects, 502."""

    def empty(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"")

    with pytest.raises(IntegrationError, match="has no header"):
        await _rows(client(empty, **_file()))

    def ragged(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"A,B\n1,x,extra\n")

    configured = client(ragged, **_file())
    with pytest.raises(IntegrationError, match="3 columns, header has 2"):
        await _rows(configured)
    assert configured.last_exchange is not None
    assert configured.last_exchange.outcome == "REFUSED"


@pytest.mark.asyncio
async def test_stream_retries_a_busy_door_and_raises_when_it_stays_busy() -> None:
    """The file door states a busy key as HTTP 429 (measured); it is retried, then raised."""
    calls = 0

    def busy_then_ok(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx2.Response(429, text="<RESULT><CODE>INFO-500</CODE></RESULT>")
        return httpx2.Response(200, content=CSV.encode())

    assert len(await _rows(client(busy_then_ok, **_file(page_size=10)))) == 1
    assert calls == 2

    def always_busy(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(429, text="<CODE>INFO-330</CODE>")

    configured = client(always_busy, **_file(max_retries=0))
    with pytest.raises(IntegrationRateLimitError):
        await _rows(configured)
    assert configured.last_exchange is not None
    assert configured.last_exchange.outcome == "RATE_LIMITED"
    assert "INFO-330" in (configured.last_exchange.response_body or "")


@pytest.mark.asyncio
async def test_stream_maps_the_other_endings_like_execute() -> None:
    """A refusal, a 5xx, a timeout and an unreachable host end a stream as they end execute."""

    def refused(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(403, text="no")

    with pytest.raises(IntegrationError, match="HTTP 403"):
        await _rows(client(refused, **_file()))

    def flaky(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(503, text="later")

    configured = client(flaky, **_file(max_retries=1))
    with pytest.raises(IntegrationError, match="HTTP 503"):
        await _rows(configured)
    assert configured.last_exchange is not None
    assert configured.last_exchange.attempts == 2

    def timeout(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow")

    with pytest.raises(IntegrationTimeoutError):
        await _rows(client(timeout, **_file(max_retries=0)))

    def unreachable(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("down")

    with pytest.raises(IntegrationError, match="unreachable"):
        await _rows(client(unreachable, **_file(max_retries=0)))


@pytest.mark.asyncio
async def test_stream_is_for_files_only() -> None:
    """A JSON operation has no file to stream: configuration error, not a request."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={})

    with pytest.raises(IntegrationConfigurationError, match="stream reads CSV only"):
        await _rows(client(handler))


def test_record_cutter_ends_a_record_only_on_balanced_quotes() -> None:
    """Pieces end wherever the wire ends them; records end where the quotes say."""
    cutter = _RecordCutter()
    assert cutter.feed('a,"one\n') == []
    assert cutter.feed('two"\r\nb,c\r\nd,') == ['a,"one\ntwo"', "b,c"]
    assert cutter.finish() == ["d,"]
    assert cutter.finish() == []


@pytest.mark.asyncio
async def test_stream_carries_the_request_id_and_retries_before_the_first_byte() -> None:
    """The inbound request id travels; a timeout and a dropped connection are retried once."""
    seen: list[str | None] = []
    attempts = {"timeout": 0, "transport": 0}

    def flaky(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.headers.get("X-Request-ID"))
        if attempts["timeout"] == 0:
            attempts["timeout"] += 1
            raise httpx2.ReadTimeout("slow")
        if attempts["transport"] == 0:
            attempts["transport"] += 1
            raise httpx2.ConnectError("reset")
        return httpx2.Response(200, content=b"A,B\n1,x")

    structlog.contextvars.bind_contextvars(request_id="req-1")
    try:
        rows = await _rows(client(flaky, **_file(max_retries=2)))
    finally:
        structlog.contextvars.clear_contextvars()
    # No trailing newline: the last record is the file's tail.
    assert rows == [[{"a": 1, "b": "x"}]]
    assert seen == ["req-1", "req-1", "req-1"]


@pytest.mark.asyncio
async def test_a_header_only_file_with_no_newline_is_an_empty_feed() -> None:
    """The header may be the whole file, and may end without a newline."""

    def header_only(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"A,B")

    assert await _rows(client(header_only, **_file())) == []


@pytest.mark.asyncio
async def test_a_file_that_ends_early_is_not_retried() -> None:
    """A body that stops is tonight's failure: recorded without a status, not re-asked.

    Nothing is handed to the reader before the body has fully arrived (the
    wire is drained first), so a second download would be safe - but the
    door's own quota is ten a day, and a body the portal cut once it will cut
    again; the pass fails and the next night asks fresh.
    """

    async def torn() -> AsyncIterator[bytes]:
        yield b"A,B\n1,x\n2,y\n3,z\n"
        raise httpx2.ReadError("torn")

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, stream=_ByteStream(torn()))

    configured = client(handler, **_file(page_size=2, max_retries=2))
    with pytest.raises(IntegrationError, match="ended early"):
        await _rows(configured)
    assert configured.last_exchange is not None
    assert configured.last_exchange.outcome == "UNREACHABLE"
    # And it carries no status. `ck_integration_call_answered` lets an
    # unanswered call hold none, so recording the 200 that opened the body
    # made Postgres refuse the log row and fail the pass for its logging -
    # measured 2026-09-20 on 축산물 생산실적, 126 s into a 3.4 M record file.
    assert configured.last_exchange.status_code is None
    assert configured.last_exchange.attempts == 1


@pytest.mark.asyncio
async def test_a_body_that_stops_arriving_is_a_timeout() -> None:
    """The log has a word for a read that ran out of time, and it is not 'unreachable'."""

    async def stalled() -> AsyncIterator[bytes]:
        yield b"A,B\n1,x\n"
        raise httpx2.ReadTimeout("stalled")

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, stream=_ByteStream(stalled()))

    configured = client(handler, **_file(page_size=2))
    with pytest.raises(IntegrationTimeoutError, match="timed out"):
        await _rows(configured)
    assert configured.last_exchange is not None
    assert (configured.last_exchange.outcome, configured.last_exchange.status_code) == (
        "TIMEOUT",
        None,
    )


class _ByteStream(httpx2.AsyncByteStream):
    def __init__(self, source: AsyncIterator[bytes]) -> None:
        self._source = source

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for piece in self._source:
            yield piece
