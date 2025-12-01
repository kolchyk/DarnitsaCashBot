from __future__ import annotations

import asyncio
import json
from uuid import UUID

import httpx

from libs.common import configure_logging, get_settings
from libs.common.messaging import MessageBroker, QueueNames
from libs.data import async_session_factory
from libs.data.models import Receipt


async def process_message(broker: MessageBroker, payload: dict) -> None:
    settings = get_settings()
    receipt_id = UUID(payload["receipt_id"])
    async with async_session_factory() as session:
        receipt: Receipt | None = await session.get(Receipt, receipt_id)
        if not receipt:
            return
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://ocr-mock:8081/ocr",
                json={"storage_key": payload["storage_key"], "checksum": payload["checksum"]},
                timeout=15,
            )
            response.raise_for_status()
            ocr_data = response.json()
        receipt.ocr_payload = ocr_data
        receipt.status = "processing"
        await session.commit()
    await broker.publish(
        QueueNames.OCR_RESULTS,
        {**payload, "ocr_payload": ocr_data},
    )


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    broker = MessageBroker(settings)
    while True:
        async with broker.consume(QueueNames.RECEIPTS) as queue:
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        payload = json.loads(message.body.decode("utf-8"))
                        await process_message(broker, payload)
        await asyncio.sleep(1)


def run():
    asyncio.run(run_worker())


if __name__ == "__main__":
    run()

