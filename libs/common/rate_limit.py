from __future__ import annotations

import time

import redis.asyncio as redis

from libs.common import AppSettings, get_settings


class RateLimiter:
    def __init__(
        self,
        *,
        prefix: str,
        limit: int,
        ttl_seconds: int,
        settings: AppSettings | None = None,
        redis_client: redis.Redis | None = None,
    ):
        self.prefix = prefix
        self.limit = limit
        self.ttl_seconds = ttl_seconds
        self.settings = settings or get_settings()
        self._redis = redis_client or redis.from_url(
            self.settings.redis_url, decode_responses=True
        )

    async def check(self, key: str) -> bool:
        redis_key = f"rl:{self.prefix}:{key}"
        current = await self._redis.incr(redis_key)
        if current == 1:
            await self._redis.expire(redis_key, self.ttl_seconds)
        return current <= self.limit

    async def tokens_left(self, key: str) -> int:
        redis_key = f"rl:{self.prefix}:{key}"
        current = await self._redis.get(redis_key)
        return max(self.limit - int(current or 0), 0)

