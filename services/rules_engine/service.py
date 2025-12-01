from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from libs.common import configure_logging, get_settings
from libs.common.messaging import MessageBroker, QueueNames
from libs.data import async_session_factory
from libs.data.models import LineItem, Receipt
from libs.data.repositories import ReceiptRepository

ELIGIBILITY_WINDOW_DAYS = 7
MAX_RECEIPTS_PER_DAY = 3


async def evaluate(payload: dict, broker: MessageBroker) -> None:
    receipt_id = UUID(payload["receipt_id"])
    async with async_session_factory() as session:
        receipt: Receipt | None = await session.get(Receipt, receipt_id)
        if not receipt:
            return
        ocr_payload = payload.get("ocr_payload") or {}
        
        # Проверяем, не является ли это ошибкой OCR
        if ocr_payload.get("error") or payload.get("status") == "failed":
            receipt.status = "rejected"
            await session.commit()
            await broker.publish(
                QueueNames.RULE_DECISIONS,
                {"receipt_id": str(receipt.id), "status": "rejected", "reason": "ocr_failed"},
            )
            return

        repo = ReceiptRepository(session)
        daily_count = await repo.daily_submission_count(receipt.user_id)
        if daily_count > MAX_RECEIPTS_PER_DAY:
            receipt.status = "rejected"
            await session.commit()
            await broker.publish(QueueNames.RULE_DECISIONS, {"receipt_id": str(receipt.id), "status": "rejected", "reason": "daily_limit"})
            return

        purchase_ts = ocr_payload.get("purchase_ts")
        if purchase_ts:
            receipt.purchase_ts = datetime.fromisoformat(purchase_ts)
            if receipt.purchase_ts < datetime.now(timezone.utc) - timedelta(days=ELIGIBILITY_WINDOW_DAYS):
                receipt.status = "rejected"
                await session.commit()
                await broker.publish(QueueNames.RULE_DECISIONS, {"receipt_id": str(receipt.id), "status": "rejected", "reason": "expired"})
                return

        # Принимаем все чеки, которые успешно прошли OCR
        # Распознаем и сохраняем все товары из чека
        line_items = ocr_payload.get("line_items", [])
        
        # Проверяем, что OCR успешно распознал хотя бы один товар
        has_items = len(line_items) > 0
        
        # Сохраняем все распознанные товары
        for item in line_items:
            name = item.get("name", "")
            quantity = int(item.get("quantity", 1))
            price = item.get("price")
            if price is None:
                price = 0
            else:
                price = int(price)
            confidence = float(item.get("confidence", 0))
            sku_code = item.get("sku_code")  # Используем SKU из OCR, если есть
            
            session.add(
                LineItem(
                    receipt_id=receipt.id,
                    sku_code=sku_code,
                    product_name=name,
                    quantity=quantity,
                    unit_price=price,
                    total_price=price * quantity,
                    confidence=confidence,
                )
            )
        
        # Принимаем чек, если OCR успешно распознал товары
        receipt.status = "accepted" if has_items else "rejected"
        await session.commit()
    await broker.publish(
        QueueNames.RULE_DECISIONS,
        {"receipt_id": str(receipt_id), "status": receipt.status, "eligible": receipt.status == "accepted"},
    )


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    broker = MessageBroker(settings)
    while True:
        async with broker.consume(QueueNames.OCR_RESULTS) as queue:
            async with queue.iterator() as iterator:
                async for message in iterator:
                    async with message.process():
                        payload = json.loads(message.body.decode("utf-8"))
                        await evaluate(payload, broker)
        await asyncio.sleep(1)


def run():
    asyncio.run(run_worker())


if __name__ == "__main__":
    run()

