from __future__ import annotations

import asyncio
import logging

from libs.common import get_settings
from libs.common.events import EVENT_RECEIPT_ACCEPTED, Event, get_event_bus
from libs.common.notifications import NotificationService

logger = logging.getLogger(__name__)


async def bonus_event_listener(notification_service: NotificationService) -> None:
    """Listen for receipt accepted events and trigger bonus payouts."""
    from services.bonus_service.main import trigger_payout
    
    settings = get_settings()
    event_bus = get_event_bus()
    
    async def handle_receipt_accepted(event: Event) -> None:
        """Handle receipt accepted event."""
        receipt_id = event.payload.get("receipt_id")
        if not receipt_id:
            logger.warning("Received receipt.accepted event without receipt_id")
            return
        
        try:
            from libs.common.analytics import AnalyticsClient
            from libs.common.crypto import Encryptor
            from libs.common.portmone import PortmoneDirectClient
            
            analytics = AnalyticsClient(settings)
            encryptor = Encryptor()
            client = PortmoneDirectClient(settings)
            
            try:
                await trigger_payout(
                    payload={
                        "receipt_id": receipt_id,
                        "status": "accepted",
                    },
                    analytics=analytics,
                    client=client,
                    encryptor=encryptor,
                    settings=settings,
                )
            finally:
                await client.aclose()
        except Exception as e:
            logger.error(
                f"Failed to trigger payout for receipt {receipt_id}: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
    
    # Subscribe to receipt accepted events
    await event_bus.subscribe(EVENT_RECEIPT_ACCEPTED, handle_receipt_accepted)
    logger.info("Bonus event listener started and subscribed to receipt.accepted events")
    
    # Keep the listener running
    while True:
        await asyncio.sleep(60)

