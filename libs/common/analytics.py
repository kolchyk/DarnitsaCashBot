from __future__ import annotations

import json
from datetime import datetime

import redis.asyncio as redis

from libs.common import AppSettings, get_settings


class AnalyticsClient:
    STREAM_KEY = "analytics:events"

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._redis = redis.from_url(self.settings.redis_url)

    async def record(self, event_type: str, payload: dict) -> None:
        entry = {"type": event_type, "payload": json.dumps(payload), "ts": datetime.utcnow().isoformat()}
        await self._redis.xadd(self.STREAM_KEY, entry, maxlen=10000)

