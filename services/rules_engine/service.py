from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from libs.common import configure_logging, get_settings
from libs.common.analytics import AnalyticsClient
from libs.common.crypto import Encryptor
from libs.common.portmone import PortmoneDirectClient
from libs.data import async_session_factory
from libs.data.models import LineItem, Receipt
from libs.data.repositories import ReceiptRepository

LOGGER = logging.getLogger(__name__)

ELIGIBILITY_WINDOW_DAYS = 7
MAX_RECEIPTS_PER_DAY = 3


async def evaluate(payload: dict) -> None:
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
            # RabbitMQ removed - decisions are now stored in database only
            return

        repo = ReceiptRepository(session)
        daily_count = await repo.daily_submission_count(receipt.user_id)
        if daily_count > MAX_RECEIPTS_PER_DAY:
            receipt.status = "rejected"
            await session.commit()
            # RabbitMQ removed - decisions are now stored in database only
            return

        purchase_ts = ocr_payload.get("purchase_ts")
        if purchase_ts:
            receipt.purchase_ts = datetime.fromisoformat(purchase_ts)
            if receipt.purchase_ts < datetime.now(timezone.utc) - timedelta(days=ELIGIBILITY_WINDOW_DAYS):
                receipt.status = "rejected"
                await session.commit()
                # RabbitMQ removed - decisions are now stored in database only
                return

        # Принимаем все чеки, которые успешно прошли OCR
        # Распознаем и сохраняем все товары из чека
        line_items = ocr_payload.get("line_items", [])
        
        # Проверяем, что OCR успешно распознал хотя бы один товар
        has_items = len(line_items) > 0
        
        # Проверяем наличие "Дарниця" в названиях товаров
        # Используем регистронезависимый поиск
        # Включаем разные падежи и варианты написания на украинском языке
        DARNITSA_KEYWORDS_CYRILLIC = [
            # Основные варианты (именительный падеж)
            "дарниця", "дарница",
            # Родительный падеж
            "дарниці",
            # Винительный падеж
            "дарницю",
            # Творительный падеж
            "дарницею",
        ]
        DARNITSA_KEYWORDS_LATIN = [
            # Латинские варианты (транслитерация через unidecode)
            "darnitsa", "darnitsia",
        ]
        has_darnitsa = False
        
        # Сохраняем все распознанные товары и проверяем наличие Дарница
        for item in line_items:
            # Используем оригинальный текст для поиска кириллицы
            original_name = item.get("original_name", item.get("name", ""))
            normalized_name = item.get("name", "")
            
            original_lower = original_name.lower()
            normalized_lower = normalized_name.lower()
            
            # Проверяем наличие Дарница в оригинальном тексте (кириллица)
            if any(keyword in original_lower for keyword in DARNITSA_KEYWORDS_CYRILLIC):
                has_darnitsa = True
            # Проверяем в нормализованном тексте (транслитерация)
            elif any(keyword in normalized_lower for keyword in DARNITSA_KEYWORDS_LATIN):
                has_darnitsa = True
            
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
        
        # Принимаем чек только если найден товар с Дарница
        receipt.status = "accepted" if (has_items and has_darnitsa) else "rejected"
        await session.commit()
        
        # Trigger bonus payout if receipt was accepted
        if receipt.status == "accepted":
            try:
                from services.bonus_service.main import trigger_payout
                settings = get_settings()
                analytics = AnalyticsClient(settings)
                encryptor = Encryptor()
                client = PortmoneDirectClient(settings)
                
                try:
                    await trigger_payout(
                        payload={
                            "receipt_id": str(receipt_id),
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
                LOGGER.error(
                    f"Failed to trigger payout for receipt {receipt_id}: {type(e).__name__}: {str(e)}",
                    exc_info=True,
                )
    # RabbitMQ removed - decisions are now stored in database only


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    # RabbitMQ removed - worker no longer consumes from queue
    # This worker should be called directly or via HTTP endpoint instead
    while True:
        await asyncio.sleep(60)  # Placeholder - no longer consuming from queue


def run():
    asyncio.run(run_worker())


if __name__ == "__main__":
    run()

