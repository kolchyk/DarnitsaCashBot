from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict

from libs.common import AppSettings, get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """In-memory rate limiter suitable for the single-process MVP deployment."""

    def __init__(
        self,
        *,
        prefix: str,
        limit: int,
        ttl_seconds: int,
        settings: AppSettings | None = None,
    ):
        self.prefix = prefix
        self.limit = limit
        self.ttl_seconds = ttl_seconds
        self.settings = settings or get_settings()
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> bool:
        async with self._lock:
            now = time.monotonic()
            bucket = self._hits[self._key(key)]
            bucket[:] = [ts for ts in bucket if now - ts < self.ttl_seconds]
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    async def tokens_left(self, key: str) -> int:
        async with self._lock:
            now = time.monotonic()
            bucket = self._hits[self._key(key)]
            bucket[:] = [ts for ts in bucket if now - ts < self.ttl_seconds]
            return max(self.limit - len(bucket), 0)

    def _key(self, key: str) -> str:
        """Generate a namespaced key for rate limiting."""
        return f"{self.prefix}:{key}"

