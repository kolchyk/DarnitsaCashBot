import time
import pytest

from libs.common.rate_limit import RateLimiter
from libs.common import get_settings


class MemoryRedis:
    def __init__(self):
        self.store: dict[str, tuple[int, float]] = {}

    async def incr(self, key: str) -> int:
        value, expiry = self.store.get(key, (0, 0))
        if expiry and time.time() > expiry:
            value = 0
        value += 1
        self.store[key] = (value, expiry)
        return value

    async def expire(self, key: str, seconds: int):
        value, _ = self.store.get(key, (0, 0))
        self.store[key] = (value, time.time() + seconds)

    async def get(self, key: str) -> int | None:
        value, expiry = self.store.get(key, (0, 0))
        if expiry and time.time() > expiry:
            self.store.pop(key, None)
            return None
        return value


@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy")
    monkeypatch.setenv("ENCRYPTION_SECRET", "secret")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    fake = MemoryRedis()
    limiter = RateLimiter(
        prefix="test",
        limit=2,
        ttl_seconds=5,
        redis_client=fake,  # type: ignore[arg-type]
        settings=get_settings(),
    )
    assert await limiter.check("user1")
    assert await limiter.check("user1")
    assert not await limiter.check("user1")


@pytest.mark.asyncio
async def test_rate_limiter_resets_after_ttl(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy")
    monkeypatch.setenv("ENCRYPTION_SECRET", "secret")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    fake = MemoryRedis()
    limiter = RateLimiter(
        prefix="test",
        limit=1,
        ttl_seconds=1,
        redis_client=fake,  # type: ignore[arg-type]
        settings=get_settings(),
    )
    assert await limiter.check("user1")
    assert not await limiter.check("user1")
    await fake.expire("rl:test:user1", 0)
    assert await limiter.check("user1")

