from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from libs.common import configure_logging, get_settings
from libs.common.messaging import MessageBroker, QueueNames
from libs.data import async_session_factory
from libs.data.models import LineItem, Receipt
from libs.data.repositories import CatalogRepository, ReceiptRepository
from .matcher import is_receipt_eligible

ELIGIBILITY_WINDOW_DAYS = 7
MAX_RECEIPTS_PER_DAY = 3


async def evaluate(payload: dict, broker: MessageBroker) -> None:
    receipt_id = UUID(payload["receipt_id"])
    async with async_session_factory() as session:
        receipt: Receipt | None = await session.get(Receipt, receipt_id)
        if not receipt:
            return
        ocr_payload = payload.get("ocr_payload") or {}

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

        catalog_repo = CatalogRepository(session)
        catalog = await catalog_repo.list_active()
        aliases = {item.sku_code: [alias.lower() for alias in item.product_aliases] for item in catalog}

        line_items = ocr_payload.get("line_items", [])
        matched = is_receipt_eligible(aliases, line_items)
        for item in line_items:
            name = item.get("name", "").lower()
            quantity = int(item.get("quantity", 1))
            price = int(item.get("price", 0))
            confidence = float(item.get("confidence", 0))
            sku_code = None
            for code, alias_list in aliases.items():
                if any(alias in name for alias in alias_list):
                    sku_code = code
                    break
            session.add(
                LineItem(
                    receipt_id=receipt.id,
                    sku_code=sku_code,
                    product_name=item.get("name", ""),
                    quantity=quantity,
                    unit_price=price,
                    total_price=price * quantity,
                    confidence=confidence,
                )
            )
        receipt.status = "accepted" if matched else "rejected"
        await session.commit()
    await broker.publish(
        QueueNames.RULE_DECISIONS,
        {"receipt_id": str(receipt_id), "status": receipt.status, "eligible": matched},
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

