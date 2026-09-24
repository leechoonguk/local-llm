"""walk_operation: a paging operation read whole, one page per yield.

One rule ends the walk, whatever the portal - a page shorter than the window.
A refusal the caller names as an end code is that rule too, and a spent key
pool is a wait, not an ending. The family comes off the operation's own
REQUEST fields, so the tests configure a window and watch which paths go out.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import httpx2
import pytest

from app.core.exceptions import (
    IntegrationConfigurationError,
    IntegrationError,
    IntegrationQuotaError,
)
from app.core.integration import IntegrationExecutionResult, IntegrationPage
from app.services.integration.operation import IntegrationOperationService
from app.services.integration.provider import IntegrationProviderService
from tests.services.integration.helpers import (
    configured_integration,
    configured_operation,
    request_field,
    response_field,
)


ENVELOPE = {
    "direction": "RESPONSE",
    "location": "ENVELOPE",
    "key": "result_code",
    "wire_path": "/RESULT/CODE",
    "value_type": "STRING",
    "required": True,
    "match_mode": "ONE_OF",
    "expected_values": ["INFO-000"],
}


def _ranged(fields=None, **updates):
    """A portal paging by row interval, the records under `/rows`."""
    return configured_operation(
        code="feed",
        path_template="/feed/{range_start}/{range_end}",
        response_root="/rows",
        fields=fields
        or [
            request_field(
                key="range_start", wire_path="range_start", location="PATH", value_type="INTEGER"
            ),
            request_field(
                key="range_end", wire_path="range_end", location="PATH", value_type="INTEGER"
            ),
            ENVELOPE,
            response_field(key="name", wire_path="/name", required=False),
        ],
        **{"page_size": 2, **updates},
    )


async def _create(session, operation=None) -> None:
    await IntegrationProviderService(session).create_integration(
        configured_integration(code="portal", operations=[operation or _ranged()]), "tester"
    )
    await session.rollback()


def _names(pages: list[IntegrationPage]) -> list[list[object]]:
    """The rows of every page by name, the way the portal served them."""
    return [[cast(dict[str, object], row)["name"] for row in page.records] for page in pages]


def _portal(names: list[str], *, end_code: str | None = None):
    """Rows 1..n by name; a window past the end is empty, or the refusal `end_code`."""
    asked: list[tuple[int, int]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        _, _, start, end = request.url.path.split("/")
        asked.append((int(start), int(end)))
        rows = [{"name": name} for name in names[int(start) - 1 : int(end)]]
        if not rows and end_code is not None:
            return httpx2.Response(200, json={"RESULT": {"CODE": end_code}})
        return httpx2.Response(200, json={"RESULT": {"CODE": "INFO-000"}, "rows": rows})

    return handler, asked


async def _walk(session, *, end_codes=frozenset()) -> list[IntegrationPage]:
    """Every page of the walk, in order."""
    service = IntegrationOperationService(session)
    return [
        page
        async for page in service.walk_operation(
            "portal", "feed", actor="tester", end_codes=end_codes
        )
    ]


@pytest.mark.asyncio
async def test_the_walk_ends_at_the_first_short_page(factory, monkeypatch) -> None:
    """Three rows in windows of two: (1,2) full, (3,4) short, and no (5,6)."""
    handler, asked = _portal(["a", "b", "c"])
    _use_transport(monkeypatch, handler)
    async with factory() as session:
        await _create(session)
        pages = await _walk(session)
    assert asked == [(1, 2), (3, 4)]
    assert _names(pages) == [["a", "b"], ["c"]]
    assert [page.window for page in pages] == [
        {"range_start": 1, "range_end": 2},
        {"range_start": 3, "range_end": 4},
    ]
    # Every page names the call log row that produced it.
    assert all(page.call_id is not None for page in pages)


@pytest.mark.asyncio
async def test_a_window_past_the_end_is_the_empty_page(factory, monkeypatch) -> None:
    """Two rows fill (1,2) exactly; the walk learns the end from an empty (3,4)."""
    handler, asked = _portal(["a", "b"])
    _use_transport(monkeypatch, handler)
    async with factory() as session:
        await _create(session)
        pages = await _walk(session)
    assert asked == [(1, 2), (3, 4)]
    assert [len(page.records) for page in pages] == [2, 0]


@pytest.mark.asyncio
async def test_a_refusal_named_as_an_end_code_is_the_empty_page(factory, monkeypatch) -> None:
    """The portal that refuses a window past the end (INFO-200) still ends the walk."""
    handler, asked = _portal(["a", "b"], end_code="INFO-200")
    _use_transport(monkeypatch, handler)
    async with factory() as session:
        await _create(session)
        pages = await _walk(session, end_codes=frozenset({"INFO-200"}))
    assert asked == [(1, 2), (3, 4)]
    assert [len(page.records) for page in pages] == [2, 0]
    assert pages[-1].call_id is not None


@pytest.mark.asyncio
async def test_any_other_refusal_ends_the_walk_with_the_error(factory, monkeypatch) -> None:
    """A code the caller did not name is the provider's verdict, raised as it is."""
    handler, _ = _portal(["a", "b"], end_code="ERROR-300")
    _use_transport(monkeypatch, handler)
    async with factory() as session:
        await _create(session)
        with pytest.raises(IntegrationError) as raised:
            await _walk(session, end_codes=frozenset({"INFO-200"}))
        assert raised.value.envelope_value == "ERROR-300"


@pytest.mark.asyncio
async def test_a_spent_pool_is_waited_out_and_the_same_window_asked_again(
    factory, monkeypatch
) -> None:
    """The quota error names when to retry; the walk sleeps until then and retries."""
    asked: list[dict[str, int]] = []
    answers = iter(
        [
            IntegrationQuotaError(
                "portal", "feed", "spent", retry_at=datetime.now(UTC) - timedelta(seconds=1)
            ),
            IntegrationExecutionResult(
                canonical_payload=[{"name": "a"}], metadata={}, status_code=200
            ),
        ]
    )
    waited: list[float] = []

    async def _execute(self, provider_code, operation_code, inputs, *, actor, client=None):
        asked.append(dict(inputs))
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer, None

    async def _sleep(seconds: float) -> None:
        waited.append(seconds)

    monkeypatch.setattr(IntegrationOperationService, "execute_operation", _execute)
    monkeypatch.setattr("app.services.integration.operation.asyncio.sleep", _sleep)
    async with factory() as session:
        await _create(session)
        pages = await _walk(session)
    assert asked == [{"range_start": 1, "range_end": 2}] * 2
    assert waited == [0]
    assert _names(pages) == [["a"]]


@pytest.mark.asyncio
async def test_one_record_through_absolute_pointers_is_a_page_of_one(factory, monkeypatch) -> None:
    """A payload that is one mapping is one record, not its keys."""

    async def _execute(self, provider_code, operation_code, inputs, *, actor, client=None):
        return (
            IntegrationExecutionResult(
                canonical_payload={"name": "a"}, metadata={}, status_code=200
            ),
            None,
        )

    monkeypatch.setattr(IntegrationOperationService, "execute_operation", _execute)
    async with factory() as session:
        await _create(session)
        pages = await _walk(session)
    assert [page.records for page in pages] == [[{"name": "a"}]]


@pytest.mark.asyncio
async def test_an_operation_without_a_paging_family_cannot_be_walked(factory) -> None:
    """Nothing to widen: the walk refuses before the first call."""
    async with factory() as session:
        await _create(session, configured_operation(code="feed"))
        with pytest.raises(IntegrationConfigurationError, match="no paging family"):
            await _walk(session)


def _use_transport(monkeypatch, handler) -> None:
    """Route every execute_operation of the walk through the portal's transport."""
    original = IntegrationOperationService.execute_operation

    async def _execute(self, provider_code, operation_code, inputs, *, actor, client=None):
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
            return await original(
                self, provider_code, operation_code, inputs, actor=actor, client=client
            )

    monkeypatch.setattr(IntegrationOperationService, "execute_operation", _execute)
