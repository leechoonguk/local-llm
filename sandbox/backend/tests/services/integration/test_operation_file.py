"""walk_operation over a file: the whole feed in one answer, a page per chunk.

A CSV operation has no window to widen and no envelope to check: the walk is
`stream`, and every chunk of `page_size` records is one page numbered as the
row interval it holds, so the step log reads the same rows a windowed walk's
does. One call record is written, after the last chunk.
"""

from __future__ import annotations

import gzip
from typing import cast

import httpx2
import pytest
import sqlalchemy as sa

from app.core.exceptions import IntegrationConfigurationError
from app.models.integration.call import IntegrationCall
from app.services.integration.operation import IntegrationOperationService
from app.services.integration.provider import IntegrationProviderService
from tests.services.integration.helpers import (
    configured_integration,
    configured_operation,
    response_field,
)


CSV = "name\r\na\r\nb\r\nc\r\n"


def _file(**updates):
    return configured_operation(
        **{
            "code": "feed",
            "path_template": "/feed/file",
            "response_format": "CSV",
            "fields": [response_field(key="name", wire_path="/name", required=False)],
            "page_size": 2,
            **updates,
        }
    )


async def _create(session, operation) -> None:
    await IntegrationProviderService(session).create_integration(
        configured_integration(code="portal", operations=[operation]), "tester"
    )
    await session.rollback()


def _use_transport(monkeypatch, handler) -> None:
    """Route the walk's one stream through the portal's transport."""
    real_client_cls = httpx2.AsyncClient
    monkeypatch.setattr(
        httpx2, "AsyncClient", lambda: real_client_cls(transport=httpx2.MockTransport(handler))
    )


@pytest.mark.asyncio
async def test_a_file_walks_as_chunks_and_logs_one_call(factory, monkeypatch) -> None:
    """Three records in chunks of two: (1,2) then (3,4), and one call for both."""
    asked: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        asked.append(request.url.path)
        return httpx2.Response(
            200,
            content=gzip.compress(CSV.encode()),
            headers={"content-type": "application/gzip"},
        )

    _use_transport(monkeypatch, handler)
    async with factory() as session:
        await _create(session, _file())
        service = IntegrationOperationService(session)
        pages = [
            page
            async for page in service.walk_operation(
                "portal", "feed", actor="tester", end_codes=frozenset()
            )
        ]
        assert [page.window for page in pages] == [
            {"range_start": 1, "range_end": 2},
            {"range_start": 3, "range_end": 4},
        ]
        names = [[cast(dict[str, object], row)["name"] for row in page.records] for page in pages]
        assert names == [["a", "b"], ["c"]]
        assert all(page.call_id is None for page in pages)
        assert asked == ["/feed/file"]

    async with factory() as session:
        calls = (await session.execute(sa.select(IntegrationCall))).scalars().all()
        assert [call.outcome for call in calls] == ["SUCCESS"]
        size = len(gzip.compress(CSV.encode()))
        assert calls[0].response_body == f"<application/gzip {size} bytes>"


@pytest.mark.asyncio
async def test_a_file_operation_refuses_the_three_shapes_that_cannot_apply(factory) -> None:
    """A root, an envelope row and a paging input are each refused at write time."""
    envelope = {
        "direction": "RESPONSE",
        "location": "ENVELOPE",
        "key": "result_code",
        "wire_path": "/RESULT/CODE",
        "value_type": "STRING",
        "required": True,
        "match_mode": "ONE_OF",
        "expected_values": ["INFO-000"],
    }
    async with factory() as session:
        for operation, message in [
            (_file(response_root="/rows"), "no response root"),
            (
                _file(fields=[envelope, response_field(key="name", wire_path="/name")]),
                "no envelope",
            ),
            (
                _file(
                    fields=[
                        response_field(key="name", wire_path="/name"),
                        {
                            "direction": "REQUEST",
                            "location": "PATH",
                            "key": "range_start",
                            "wire_path": "range_start",
                            "value_source": "CALLER",
                            "value_type": "INTEGER",
                            "required": True,
                        },
                        {
                            "direction": "REQUEST",
                            "location": "PATH",
                            "key": "range_end",
                            "wire_path": "range_end",
                            "value_source": "CALLER",
                            "value_type": "INTEGER",
                            "required": True,
                        },
                    ]
                ),
                "not windowed",
            ),
            (
                _file(fields=[response_field(key="name", wire_path="/deep/name")]),
                "one-segment pointer",
            ),
        ]:
            with pytest.raises(IntegrationConfigurationError, match=message):
                await _create(session, operation)
