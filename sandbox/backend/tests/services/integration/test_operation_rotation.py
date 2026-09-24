"""The key pool is invisible from the caller up.

A provider whose secrets share a `rotation_group` answers as one credential:
the service sends the next member, sits a member out when the provider says
its quota is spent, and only refuses when every member has. Each try is a call
log row that names its key - the name, never the value.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from sqlalchemy import select

from app.core.exceptions import (
    IntegrationConfigurationError,
    IntegrationError,
    IntegrationQuotaError,
)
from app.models.integration.call import IntegrationCall
from app.models.integration.secret import IntegrationSecret
from app.services.integration.operation import IntegrationOperationService
from app.services.integration.provider import IntegrationProviderService
from tests.services.integration.helpers import configured_integration, configured_operation


QUOTA_CODE = "INFO-320"

# What 식품안전나라 answers between 09:00 and 19:00 KST, and the window revision
# 258 seeds for it: ten hours, the length of the shut period.
DAYTIME_BLOCK_CODE = "ERROR-503"
DAYTIME_BLOCK_SECONDS = 36000
KEYS = {"key-a": "value-a", "key-b": "value-b", "key-c": "value-c"}
NAMES = {value: name for name, value in KEYS.items()}


def _pooled_integration(*, quota_codes: dict[str, int] | None = None, grouped: bool = True):
    """Three interchangeable keys, sent as a path segment, behind one verdict.

    `grouped=False` is the provider without a pool: the same keys, none of
    them a rotation member, so every call goes out with `key-a`.
    """
    fields = [
        {
            "direction": "REQUEST",
            "location": "PATH",
            "key": "service_key",
            "wire_path": "service_key",
            "value_source": "SECRET",
            "secret_name": "key-a",
            "value_type": "STRING",
            "required": True,
        },
        {
            "direction": "RESPONSE",
            "location": "ENVELOPE",
            "key": "result_code",
            "wire_path": "/RESULT/CODE",
            "value_type": "STRING",
            "required": True,
            "match_mode": "ONE_OF",
            "expected_values": ["INFO-000"],
        },
        {
            "direction": "RESPONSE",
            "location": "BODY",
            "key": "value",
            "wire_path": "/value",
            "value_type": "STRING",
            "required": False,
        },
    ]
    operation = configured_operation(
        code="fetch",
        path_template="/api/{service_key}/fetch",
        fields=fields,
        quota_codes={"INFO-320": 3600} if quota_codes is None else quota_codes,
    )
    secrets = [
        {"name": name, "value": value, "rotation_group": "service-key" if grouped else None}
        for name, value in KEYS.items()
    ]
    return configured_integration(code="portal", operations=[operation], secrets=secrets)


def _handler(spent: set[str], seen: list[str]):
    """A portal whose quota is per key: a spent key answers the quota code."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        # The path carries the value; the test reasons in names.
        key = NAMES[request.url.path.split("/")[2]]
        seen.append(key)
        if key in spent:
            return httpx2.Response(200, json={"RESULT": {"CODE": QUOTA_CODE}})
        return httpx2.Response(200, json={"RESULT": {"CODE": "INFO-000"}, "value": key})

    return handler


async def _create(session, **kwargs) -> None:
    await IntegrationProviderService(session).create_integration(
        _pooled_integration(**kwargs), "tester"
    )
    await session.rollback()


async def _execute(session, handler):
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    try:
        return await IntegrationOperationService(session).execute_operation(
            "portal", "fetch", {}, actor="tester", client=client
        )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_a_spent_key_is_skipped_and_the_same_request_goes_out_with_the_next(
    factory,
) -> None:
    """Spent keys cost extra calls and no error; the fresh one answers.

    The round-robin starts at a random member per process, so how many spent
    keys are met before the fresh one is not the contract - that every met
    one is logged, marked, and never the value, is.
    """
    async with factory() as session:
        await _create(session)
        seen: list[str] = []
        result, call_id = await _execute(session, _handler({"key-a", "key-b"}, seen))
        assert result.canonical_payload == {"value": "key-c"}
        assert seen[-1] == "key-c"
        assert len(seen) == len(set(seen))
        # Every try is a log row naming its key by name only.
        rows = (
            (await session.execute(select(IntegrationCall).order_by(IntegrationCall.created_at)))
            .scalars()
            .all()
        )
        assert [(row.secret_name, row.outcome) for row in rows] == [
            (key, "REFUSED" if key != "key-c" else "SUCCESS") for key in seen
        ]
        assert call_id == rows[-1].id
        assert not any(value in row.url for row in rows for value in KEYS.values())
        # The met spent members sit out; the one that answered does not.
        secrets = (await session.execute(select(IntegrationSecret))).scalars().all()
        marked = {secret.name for secret in secrets if secret.exhausted_until is not None}
        assert marked == set(seen) - {"key-c"}


@pytest.mark.asyncio
async def test_every_key_spent_is_the_provider_refusal_the_caller_already_handles(
    factory,
) -> None:
    """The refusal comes as the quota error, and it names when the pool comes back."""
    async with factory() as session:
        await _create(session)
        seen: list[str] = []
        with pytest.raises(IntegrationQuotaError) as raised:
            await _execute(session, _handler(set(KEYS), seen))
        assert raised.value.envelope_value == QUOTA_CODE
        assert sorted(seen) == sorted(KEYS)
        # Every member sits out, the last one included - the next call must not
        # open with a key this one just proved spent. The marks were written on
        # their own session, so this one's loaded rows are expired first.
        session.expire_all()
        secrets = (await session.execute(select(IntegrationSecret))).scalars().all()
        assert all(secret.exhausted_until is not None for secret in secrets)
        # `retry_at` is the earliest return of the pool, in UTC whatever the
        # engine hands back.
        earliest = min(secret.exhausted_until for secret in secrets)  # type: ignore[type-var]
        assert raised.value.retry_at == earliest.replace(tzinfo=UTC)


@pytest.mark.asyncio
async def test_a_provider_without_a_pool_names_the_code_s_own_window(factory) -> None:
    """One ungrouped key: nothing to rotate to, nothing marked, retry after the sit-out."""
    async with factory() as session:
        await _create(session, grouped=False)
        seen: list[str] = []
        before = datetime.now(UTC)
        with pytest.raises(IntegrationQuotaError) as raised:
            await _execute(session, _handler(set(KEYS), seen))
        assert seen == ["key-a"]
        assert before + timedelta(seconds=3600) <= raised.value.retry_at
        assert raised.value.retry_at <= datetime.now(UTC) + timedelta(seconds=3600)
        secrets = (await session.execute(select(IntegrationSecret))).scalars().all()
        assert all(secret.exhausted_until is None for secret in secrets)


@pytest.mark.asyncio
async def test_a_member_still_inside_its_window_is_not_a_candidate(factory) -> None:
    """The mark outlives the process: a fresh service skips a key marked earlier."""
    async with factory() as session:
        await _create(session)
        seen: list[str] = []
        with pytest.raises(IntegrationError):
            await _execute(session, _handler(set(KEYS), seen))
        seen.clear()
        # Two keys recover, one is still inside its hour.
        secrets = (await session.execute(select(IntegrationSecret))).scalars().all()
        for secret in secrets:
            if secret.name != "key-b":
                secret.exhausted_until = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
        result, _ = await _execute(session, _handler(set(), seen))
        assert "key-b" not in seen
        assert result.canonical_payload in ({"value": "key-a"}, {"value": "key-c"})


@pytest.mark.asyncio
async def test_a_refusal_that_is_not_the_quota_code_does_not_turn_the_pool(factory) -> None:
    """A wrong answer with a fresh key is still a wrong answer - one call, one error."""
    async with factory() as session:
        await _create(session)
        seen: list[str] = []

        def handler(request: httpx2.Request) -> httpx2.Response:
            seen.append(request.url.path.split("/")[2])
            return httpx2.Response(200, json={"RESULT": {"CODE": "ERROR-300"}})

        with pytest.raises(IntegrationError):
            await _execute(session, handler)
        assert len(seen) == 1


@pytest.mark.asyncio
async def test_a_quota_code_cannot_also_be_an_accepted_verdict(factory) -> None:
    """A code that is "success" and "spent" at once would never turn the pool."""
    async with factory() as session:
        with pytest.raises(IntegrationConfigurationError, match="INFO-000"):
            await IntegrationProviderService(session).create_integration(
                _pooled_integration(quota_codes={"INFO-000": 60}), "tester"
            )


@pytest.mark.asyncio
async def test_a_sit_out_of_zero_is_refused(factory) -> None:
    """A key that sits out for no time is sent again on the next try - the same refusal."""
    async with factory() as session:
        with pytest.raises(IntegrationConfigurationError, match="positive"):
            await IntegrationProviderService(session).create_integration(
                _pooled_integration(quota_codes={"INFO-320": 0}), "tester"
            )


@pytest.mark.asyncio
async def test_the_sit_out_is_the_code_s_own(factory) -> None:
    """A busy key returns in a minute; a spent one in an hour - the code says which."""
    async with factory() as session:
        await _create(session, quota_codes={"INFO-320": 3600, "INFO-500": 60})
        busy = "key-a"

        def handler(request: httpx2.Request) -> httpx2.Response:
            key = NAMES[request.url.path.split("/")[2]]
            code = "INFO-500" if key == busy else "INFO-000"
            return httpx2.Response(200, json={"RESULT": {"CODE": code}, "value": key})

        result, _ = await _execute(session, handler)
        assert result.canonical_payload != {"value": busy}
        secrets = (await session.execute(select(IntegrationSecret))).scalars().all()
        marked = {s.name: s.exhausted_until for s in secrets if s.exhausted_until is not None}
        assert set(marked) <= {busy}
        # The in-memory engine hands the column back naive; compare in UTC either way.
        now = datetime.now(UTC)
        for until in marked.values():
            reference = now if until.tzinfo is not None else now.replace(tzinfo=None)
            assert until - reference < timedelta(seconds=61)


@pytest.mark.asyncio
async def test_a_service_shut_for_the_day_is_waited_out_not_failed(factory) -> None:
    """식품안전나라 answers ERROR-503 from 09:00 to 19:00 KST; that is a wait, not a failure.

    Measured 2026-09-15: a run that met it mid-walk failed the feed it was on
    and nine more inside two seconds. Seeded as a quota code, the same refusal
    reaches the caller as the error a walk sleeps on and asks the same window
    again after.
    """
    async with factory() as session:
        await _create(session, quota_codes={DAYTIME_BLOCK_CODE: DAYTIME_BLOCK_SECONDS})

        def handler(request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(
                200,
                json={
                    "RESULT": {
                        "CODE": DAYTIME_BLOCK_CODE,
                        "MSG": "09시~19시에는 서비스가 제한됩니다. 이용에 참고바랍니다.",
                    }
                },
            )

        with pytest.raises(IntegrationQuotaError) as refusal:
            await _execute(session, handler)

    waits = refusal.value.retry_at - datetime.now(UTC)
    assert timedelta(hours=9) < waits <= timedelta(seconds=DAYTIME_BLOCK_SECONDS)
