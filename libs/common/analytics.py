from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import redis.asyncio as redis
import redis.exceptions

from libs.common import AppSettings, get_settings
from libs.common.rate_limit import create_redis_client

logger = logging.getLogger(__name__)


class AnalyticsClient:
    STREAM_KEY = "analytics:events"

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._redis = create_redis_client(
            self.settings.redis_url, decode_responses=False, settings=self.settings
        )

    async def record(self, event_type: str, payload: dict) -> None:
        """
        Record an analytics event to Redis stream.
        
        On Redis connection errors, fails silently (logs warning) to avoid
        breaking the service when Redis is unavailable.
        """
        entry = {
            "type": event_type,
            "payload": json.dumps(payload),
            "ts": datetime.now(timezone.utc).isoformat()
        }
        try:
            await self._redis.xadd(self.STREAM_KEY, entry, maxlen=10000)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, OSError) as e:
            logger.warning(
                f"Redis connection error in analytics.record for event {event_type}: {e}. "
                "Failing silently (event not recorded)."
            )
            # Fail silently: don't break the request when Redis is unavailable
        except Exception as e:
            logger.error(
                f"Unexpected error in analytics.record for event {event_type}: {e}. "
                "Failing silently (event not recorded).",
                exc_info=True
            )
            # Fail silently: don't break the request on unexpected errors

