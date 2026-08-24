# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import json
from typing import Any

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError


# ============================================================
# Constants
# ============================================================

logger = structlog.get_logger(__name__)


# ============================================================
# Classes
# ============================================================

class RedisCache:
    """JSON cache backed by Redis with explicit TTLs and namespace invalidation."""

    def __init__(self, client: Redis) -> None:
        self.client = client

    async def get_json(self, key: str) -> Any | None:
        try:
            payload = await self.client.get(key)
        except RedisError:
            logger.warning("redis_cache_read_failed", key=key)
            return None
        if payload is None:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("redis_cache_payload_invalid", key=key)
            return None

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        try:
            await self.client.set(key, json.dumps(value, separators=(",", ":")), ex=ttl_seconds)
        except RedisError:
            logger.warning("redis_cache_write_failed", key=key)

    async def invalidate(self, prefix: str) -> None:
        try:
            keys = [key async for key in self.client.scan_iter(match=f"{prefix}:*")]
            if keys:
                await self.client.delete(*keys)
        except RedisError:
            logger.warning("redis_cache_invalidation_failed", prefix=prefix)

    async def aclose(self) -> None:
        try:
            await self.client.aclose()
        except RedisError:
            logger.warning("redis_cache_close_failed")


# ============================================================
# Functions
# ============================================================

def scoped_cache_key(namespace: str, subject_id: str, suffix: str) -> str:
    """Build a versioned cache key isolated to one authenticated subject."""
    return f"{namespace}:v1:{subject_id}:{suffix}"
