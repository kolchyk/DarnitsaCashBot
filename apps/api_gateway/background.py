from __future__ import annotations

import asyncio
import json

from libs.common import get_settings
from libs.common.notifications import NotificationService
from libs.data.models import ReceiptStatus


async def bonus_event_listener(notification_service: NotificationService):
    # RabbitMQ removed - bonus events are now handled synchronously
    while True:
        await asyncio.sleep(60)  # Placeholder - no longer consuming from queue


async def reminder_job(notification_service: NotificationService):
    while True:
        await asyncio.sleep(60 * 60)  # placeholder hourly reminder scan
        # Pull pending reminders from DB/storage in future enhancement.


def _format_payout_message(payload: dict) -> str:
    status = payload.get("status")
    bill_id = payload.get("bill_id") or "-"
    error_description = payload.get("error_description")
    error_code = payload.get("error_code")

    if status == ReceiptStatus.PAYOUT_PENDING:
        return f"PortmoneDirect: processing top-up (bill {bill_id})."
    if status == ReceiptStatus.PAYOUT_SUCCESS:
        return f"PortmoneDirect: top-up completed ✅ (bill {bill_id})."

    reason = error_description or error_code or "unknown error"
    return f"PortmoneDirect: top-up failed ({reason})."

