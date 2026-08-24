"""Cache behaviour: per-subject keys, TTL on writes, and degradation when down."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import cast

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.cache import RedisCache, scoped_cache_key


class FakeRedis:
    """An in-process stand-in that records TTLs and honours glob scans."""

    def __init__(self) -> None:
        """Start with no keys, no TTLs, and the connection open."""
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.closed = False

    async def get(self, key: str) -> str | None:
        """Return the raw stored string, or None on a miss."""
        return self.values.get(key)

    async def set(self, key: str, value: str, *, ex: int) -> None:
        """Store the string and keep the expiry the caller asked for."""
        self.values[key] = value
        self.ttls[key] = ex

    async def scan_iter(self, *, match: str):
        """Yield keys matching the glob, as the real client does."""
        for key in list(self.values):
            if fnmatch(key, match):
                yield key

    async def delete(self, *keys: str) -> None:
        """Remove the keys and their expiries."""
        for key in keys:
            self.values.pop(key, None)
            self.ttls.pop(key, None)

    async def aclose(self) -> None:
        """Record that the cache closed its connection."""
        self.closed = True


class FailingRedis:
    """A client where every call raises, standing in for an unreachable Redis."""

    async def get(self, key: str) -> str | None:
        """Fail the read."""
        raise RedisError("down")

    async def set(self, key: str, value: str, *, ex: int) -> None:
        """Fail the write."""
        raise RedisError("down")

    async def scan_iter(self, *, match: str):
        """Fail the scan an invalidation walks."""
        raise RedisError("down")
        yield match

    async def aclose(self) -> None:
        """Fail even the shutdown path."""
        raise RedisError("down")


def _cache(client: FakeRedis | FailingRedis) -> RedisCache:
    return RedisCache(cast(Redis, client))


def test_scoped_cache_key_isolated_by_subject_and_version() -> None:
    """Two accounts asking the same question get different keys.

    A key without the subject would serve one user's rows to another; the
    version segment is what lets a shape change retire old entries.
    """
    assert scoped_cache_key("items", "user-a", "list:0:50") == "items:v1:user-a:list:0:50"
    assert scoped_cache_key("items", "user-b", "list:0:50") == "items:v1:user-b:list:0:50"


@pytest.mark.asyncio
async def test_redis_cache_degrades_when_unavailable_or_corrupt() -> None:
    """A cache outage or a bad value must not become a request failure.

    Reads answer None so the caller falls back to the database, and writes,
    invalidation and shutdown stay silent.
    """
    client = FakeRedis()
    cache = _cache(client)
    client.values["items:invalid"] = "not-json"

    assert await cache.get_json("items:invalid") is None

    unavailable = _cache(FailingRedis())
    assert await unavailable.get_json("items:list:0:50") is None
    await unavailable.set_json("items:list:0:50", [], ttl_seconds=60)
    await unavailable.invalidate("items")
    await unavailable.aclose()


@pytest.mark.asyncio
async def test_redis_cache_serializes_values_with_ttl() -> None:
    """A stored value comes back equal, and it expires.

    A write without expiry keeps a stale row until the next deploy.
    """
    client = FakeRedis()
    cache = _cache(client)

    await cache.set_json("items:list:0:50", [{"name": "Alpha"}], ttl_seconds=60)

    assert await cache.get_json("items:list:0:50") == [{"name": "Alpha"}]
    assert await cache.get_json("items:missing") is None
    assert client.ttls["items:list:0:50"] == 60


@pytest.mark.asyncio
async def test_redis_cache_invalidates_a_namespace_and_closes() -> None:
    """Invalidation drops one namespace and leaves its neighbour alone.

    Too broad a pattern turns every write into a full cache flush; the unknown
    prefix proves invalidating nothing is not an error.
    """
    client = FakeRedis()
    cache = _cache(client)
    await cache.set_json("items:list:0:50", [], ttl_seconds=60)
    await cache.set_json("items:detail:1", {"name": "Alpha"}, ttl_seconds=60)
    await cache.set_json("tasks:list:0:50", [], ttl_seconds=60)

    await cache.invalidate("items")
    await cache.invalidate("missing")
    await cache.aclose()

    assert client.values == {"tasks:list:0:50": "[]"}
    assert client.closed
