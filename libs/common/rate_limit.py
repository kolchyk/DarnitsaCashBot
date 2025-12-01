from __future__ import annotations

from urllib.parse import urlparse

import redis.asyncio as redis

from libs.common import AppSettings, get_settings


def create_redis_client(
    redis_url: str,
    decode_responses: bool = True,
    settings: AppSettings | None = None,
) -> redis.Redis:
    """
    Create a Redis client with proper SSL configuration for Heroku Redis.
    
    Args:
        redis_url: Redis connection URL
        decode_responses: Whether to decode responses as strings
        settings: Optional settings object (unused, kept for compatibility)
        
    Returns:
        Configured Redis client
    """
    # Detect Heroku Redis by URL scheme (rediss:// uses SSL)
    parsed = urlparse(redis_url)
    is_heroku_redis = parsed.scheme == "rediss"
    
    if is_heroku_redis:
        # Heroku Redis uses SSL with self-signed certificates
        # For redis-py 7.x, use ssl_cert_reqs as string "none" instead of ssl.CERT_NONE
        # The rediss:// scheme automatically enables SSL
        return redis.from_url(
            redis_url,
            decode_responses=decode_responses,
            ssl_cert_reqs="none",
        )
    
    return redis.from_url(redis_url, decode_responses=decode_responses)


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
        self._redis = redis_client or create_redis_client(
            self.settings.redis_url, decode_responses=True, settings=self.settings
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

