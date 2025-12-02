from __future__ import annotations

import logging
from datetime import datetime, timezone

from libs.common import AppSettings, get_settings

logger = logging.getLogger(__name__)


class AnalyticsClient:
    """Lightweight logger-backed analytics client used during MVP."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()

    async def record(self, event_type: str, payload: dict) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("analytics.%s ts=%s payload=%s", event_type, timestamp, payload)

