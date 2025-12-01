from __future__ import annotations

import json
from contextlib import asynccontextmanager

import aio_pika

from libs.common import AppSettings, get_settings


class QueueNames:
    RECEIPTS = "receipts.incoming"
    OCR_RESULTS = "receipts.ocr.results"
    RULE_DECISIONS = "receipts.rules.decisions"
    BONUS_REQUESTS = "bonus.requests"
    BONUS_EVENTS = "bonus.events"


class MessageBroker:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()

    async def publish(self, queue: str, payload: dict) -> None:
        async with self._connection() as connection:
            channel = await connection.channel()
            message = aio_pika.Message(body=json.dumps(payload).encode("utf-8"))
            await channel.default_exchange.publish(message, routing_key=queue)

    @asynccontextmanager
    async def consume(self, queue: str):
        async with self._connection() as connection:
            channel = await connection.channel()
            queue_obj = await channel.declare_queue(queue, durable=True)
            yield queue_obj

    def _connection(self):
        return aio_pika.connect_robust(
            host=self.settings.rabbitmq_host,
            port=self.settings.rabbitmq_port,
            login=self.settings.rabbitmq_user,
            password=self.settings.rabbitmq_password,
        )

