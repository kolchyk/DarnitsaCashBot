"""Event system for loose coupling between services."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Base event class."""
    event_type: str
    payload: dict[str, Any]


class EventBus:
    """Simple in-memory event bus for decoupling services."""
    
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[Event], Awaitable[None]]]] = {}
        self._lock = asyncio.Lock()
    
    async def subscribe(self, event_type: str, handler: Callable[[Event], Awaitable[None]]) -> None:
        """Subscribe a handler to an event type."""
        async with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
            logger.debug(f"Subscribed handler to event type: {event_type}")
    
    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribed handlers."""
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            logger.debug(f"No handlers registered for event type: {event.event_type}")
            return
        
        logger.info(f"Publishing event: {event.event_type} to {len(handlers)} handler(s)")
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    f"Error in event handler for {event.event_type}: {type(e).__name__}: {str(e)}",
                    exc_info=True,
                )
    
    async def unsubscribe(self, event_type: str, handler: Callable[[Event], Awaitable[None]]) -> None:
        """Unsubscribe a handler from an event type."""
        async with self._lock:
            if event_type in self._handlers:
                try:
                    self._handlers[event_type].remove(handler)
                    logger.debug(f"Unsubscribed handler from event type: {event_type}")
                except ValueError:
                    logger.warning(f"Handler not found for event type: {event_type}")


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# Event type constants
EVENT_RECEIPT_ACCEPTED = "receipt.accepted"
EVENT_RECEIPT_REJECTED = "receipt.rejected"
EVENT_PAYOUT_REQUIRED = "payout.required"
