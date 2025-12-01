from __future__ import annotations

import asyncio
import json

from libs.common import get_settings
from libs.common.messaging import MessageBroker, QueueNames
from libs.common.notifications import NotificationService


async def bonus_event_listener(notification_service: NotificationService):
    settings = get_settings()
    broker = MessageBroker(settings)
    while True:
        async with broker.consume(QueueNames.BONUS_EVENTS) as queue:
            async with queue.iterator() as iterator:
                async for message in iterator:
                    async with message.process():
                        payload = json.loads(message.body.decode("utf-8"))
                        telegram_id = payload.get("telegram_id")
                        if telegram_id:
                            await notification_service.send_message(
                                chat_id=int(telegram_id),
                                text=f"Payout status: {payload.get('status')}",
                            )
        await asyncio.sleep(1)


async def reminder_job(notification_service: NotificationService):
    while True:
        await asyncio.sleep(60 * 60)  # placeholder hourly reminder scan
        # Pull pending reminders from DB/storage in future enhancement.

