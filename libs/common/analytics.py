from __future__ import annotations

import json
from datetime import datetime, timezone

import redis.asyncio as redis

from libs.common import AppSettings, get_settings
from libs.common.rate_limit import create_redis_client


class AnalyticsClient:
    STREAM_KEY = "analytics:events"

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._redis = create_redis_client(
            self.settings.redis_url, decode_responses=False, settings=self.settings
        )

    async def record(self, event_type: str, payload: dict) -> None:
        entry = {"type": event_type, "payload": json.dumps(payload), "ts": datetime.now(timezone.utc).isoformat()}
        await self._redis.xadd(self.STREAM_KEY, entry, maxlen=10000)

