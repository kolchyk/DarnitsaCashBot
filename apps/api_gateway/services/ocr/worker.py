from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import selectinload

from libs.common import get_settings
from libs.common.darnitsa import has_darnitsa_prefix
from libs.common.storage import StorageClient
from libs.data import async_session_factory
from libs.data.models import Receipt, ReceiptStatus
from sqlalchemy import select

from .qr_scanner import QRCodeNotFoundError, detect_qr_code
from .receipt_scraper import ScrapingError, scrape_receipt_data

LOGGER = logging.getLogger(__name__)


async def process_message(payload: dict) -> None:
    settings = get_settings()
    receipt_id = UUID(payload["receipt_id"])
    storage_key = payload.get("storage_key", "unknown")
    
    LOGGER.info(
        "Starting QR code processing for receipt %s, storage_key=%s",
        receipt_id,
        storage_key,
    )
    
    async with async_session_factory() as session:
        # Load receipt with user relationship to get telegram_id
        result = await session.execute(
            select(Receipt).options(selectinload(Receipt.user)).where(Receipt.id == receipt_id)
        )
        receipt: Receipt | None = result.scalar_one_or_none()
        if not receipt:
            LOGGER.warning("Receipt %s not found in database", receipt_id)
            return
        storage = StorageClient(settings)
        image_bytes = await storage.download(storage_key)
        LOGGER.info("Downloaded receipt image: %d bytes", len(image_bytes))

        try:
            # Step 1: Detect QR code
            LOGGER.debug("Starting QR code detection for receipt %s", receipt_id)
            qr_url = await asyncio.to_thread(detect_qr_code, image_bytes)
            
            if not qr_url:
                raise QRCodeNotFoundError("QR code not found in receipt image")
            
            LOGGER.info("QR code detected for receipt %s: url=%s", receipt_id, qr_url)
            
            # Send intermediate notification to user that QR code was recognized
            telegram_id = receipt.user.telegram_id if receipt.user else None
            if telegram_id:
                await _notify_qr_recognized(telegram_id, receipt_id, qr_url)
            
            # Step 2: Try to scrape receipt data from URL
            LOGGER.debug("Starting receipt scraping for receipt %s", receipt_id)
            scraped_data = None
            try:
                scraped_data = await asyncio.to_thread(scrape_receipt_data, qr_url)
                items_count = len(scraped_data.get("line_items", []))
                LOGGER.info(
                    "Scraping completed for receipt %s: merchant=%s, line_items=%d, total=%s",
                    receipt_id,
                    scraped_data.get("merchant"),
                    items_count,
                    scraped_data.get("total"),
                )
                
                # If scraping didn't find items, reject receipt
                if items_count == 0:
                    LOGGER.warning(
                        "Scraping found 0 items for receipt %s, rejecting",
                        receipt_id,
                    )
                    raise ScrapingError("No items found in receipt")
            except ScrapingError as exc:
                LOGGER.error(
                    "Scraping failed for receipt %s: %s",
                    receipt_id,
                    exc,
                )
                raise
            
        except QRCodeNotFoundError as exc:
            LOGGER.warning("QR code not found for receipt %s: %s", receipt_id, exc, exc_info=True)
            # Get telegram_id before commit to ensure user is loaded
            telegram_id = receipt.user.telegram_id if receipt.user else None
            receipt.status = ReceiptStatus.REJECTED
            failure_payload = {"error": str(exc), "type": "qr_code_not_found"}
            receipt.ocr_payload = failure_payload
            await session.commit()
            await _publish_failure(payload, failure_payload)
            if telegram_id:
                await _notify_receipt_error(telegram_id, receipt_id, "qr_code_not_found")
            else:
                LOGGER.warning("Cannot send error notification: receipt %s has no user or telegram_id", receipt_id)
            return
        except ScrapingError as exc:
            LOGGER.error("Scraping failed for receipt %s: %s", receipt_id, exc, exc_info=True)
            # Get telegram_id before commit to ensure user is loaded
            telegram_id = receipt.user.telegram_id if receipt.user else None
            receipt.status = ReceiptStatus.REJECTED
            failure_payload = {"error": str(exc), "type": "scraping_error"}
            receipt.ocr_payload = failure_payload
            await session.commit()
            await _publish_failure(payload, failure_payload)
            if telegram_id:
                await _notify_receipt_error(telegram_id, receipt_id, "scraping_error")
            else:
                LOGGER.warning("Cannot send error notification: receipt %s has no user or telegram_id", receipt_id)
            return
        except Exception as exc:
            LOGGER.error("Unexpected error processing receipt %s: %s", receipt_id, exc, exc_info=True)
            # Get telegram_id before commit to ensure user is loaded
            telegram_id = receipt.user.telegram_id if receipt.user else None
            receipt.status = ReceiptStatus.REJECTED
            failure_payload = {"error": f"Unexpected error: {str(exc)}", "type": "processing_error"}
            receipt.ocr_payload = failure_payload
            await session.commit()
            await _publish_failure(payload, failure_payload)
            if telegram_id:
                await _notify_receipt_error(telegram_id, receipt_id, "processing_error")
            else:
                LOGGER.warning("Cannot send error notification: receipt %s has no user or telegram_id", receipt_id)
            return

        # Step 3: Enrich scraped line items with Darnitsa detection
        LOGGER.debug("Enriching line items with Darnitsa detection for receipt %s", receipt_id)
        enriched_line_items = []
        for item in scraped_data.get("line_items", []):
            original_name = item.get("name", "")
            is_darnitsa = has_darnitsa_prefix(original_name)
            
            enriched_item = {
                "name": original_name,
                "original_name": original_name,
                "normalized_name": original_name.upper(),
                "quantity": item.get("quantity", 1),
                "price": item.get("price"),
                "confidence": item.get("confidence", 1.0),
                "sku_code": item.get("sku_code"),
                "sku_match_score": item.get("sku_match_score", 0.0),
                "is_darnitsa": is_darnitsa,
            }
            enriched_line_items.append(enriched_item)
        
        scraped_data["line_items"] = enriched_line_items
        
        # Log enriched line items
        if enriched_line_items:
            LOGGER.debug("Enriched line items for receipt %s:", receipt_id)
            for idx, item in enumerate(enriched_line_items, 1):
                darnitsa_info = ", is_darnitsa=True" if item.get("is_darnitsa") else ""
                LOGGER.debug(
                    "  Item %d: name='%s', quantity=%d, price=%s%s",
                    idx,
                    item.get("name", "")[:50],
                    item.get("quantity", 0),
                    item.get("price"),
                    darnitsa_info,
                )

        receipt.ocr_payload = scraped_data
        if scraped_data.get("merchant"):
            receipt.merchant = scraped_data["merchant"]
        purchase_ts = scraped_data.get("purchase_ts")
        if purchase_ts:
            receipt.purchase_ts = datetime.fromisoformat(purchase_ts)
        receipt.status = ReceiptStatus.PROCESSING
        await session.commit()
        
        LOGGER.info(
            "QR code processing completed for receipt %s: status=%s, merchant=%s, line_items=%d, total=%s",
            receipt_id,
            receipt.status,
            receipt.merchant,
            len(enriched_line_items),
            scraped_data.get("total"),
        )
        
        structured_payload = scraped_data

    # Trigger rules engine evaluation after QR code processing completes successfully
    LOGGER.debug("Triggering rules engine evaluation for receipt %s", receipt_id)
    try:
        from apps.api_gateway.services.rules.service import evaluate
        await evaluate({
            "receipt_id": str(receipt_id),
            "ocr_payload": structured_payload,
        })
        LOGGER.debug("Rules engine evaluation completed for receipt %s", receipt_id)
    except Exception as e:
        LOGGER.error(
            "Failed to evaluate receipt %s in rules engine: %s: %s",
            receipt_id,
            type(e).__name__,
            str(e),
            exc_info=True,
        )


async def _publish_failure(payload: dict, failure_payload: dict) -> None:
    # RabbitMQ removed - failures are now stored in database only
    pass


async def _notify_qr_recognized(telegram_id: int, receipt_id: UUID, qr_url: str) -> None:
    """Send notification to user that QR code was successfully recognized."""
    LOGGER.info("Attempting to send QR recognition notification to user %s for receipt %s", telegram_id, receipt_id)
    
    settings = get_settings()
    from apps.api_gateway.services.telegram_notifier import TelegramNotifier
    
    notifier = TelegramNotifier(settings)
    try:
        # Build message with QR URL as clickable link
        message = (
            "✅ <b>QR код розпізнано!</b>\n\n"
            "Ваш чек успішно розпізнано. Обробляємо дані...\n\n"
        )
        
        # Add link to the QR URL if it's a valid URL
        if qr_url.startswith(("http://", "https://")):
            message += f"🔗 <a href=\"{qr_url}\">Переглянути чек на сайті</a>"
        
        success = await notifier.send_message(telegram_id, message)
        if success:
            LOGGER.info("Successfully sent QR recognition notification to user %s for receipt %s", telegram_id, receipt_id)
        else:
            LOGGER.warning("Failed to send QR recognition notification to user %s for receipt %s", telegram_id, receipt_id)
    except Exception as e:
        LOGGER.error(
            "Exception while sending QR recognition notification to user %s for receipt %s: %s",
            telegram_id,
            receipt_id,
            e,
            exc_info=True,
        )
    finally:
        await notifier.close()


async def _notify_receipt_error(telegram_id: int, receipt_id: UUID, error_type: str) -> None:
    """Send error notification to user via Telegram."""
    LOGGER.info("Attempting to send error notification to user %s for receipt %s (error_type=%s)", telegram_id, receipt_id, error_type)
    
    settings = get_settings()
    from apps.api_gateway.services.telegram_notifier import TelegramNotifier
    
    notifier = TelegramNotifier(settings)
    try:
        if error_type == "qr_code_not_found":
            message = (
                "❌ <b>Чек не розпізнано</b>\n\n"
                "На жаль, не вдалося знайти QR код на зображенні чека.\n\n"
                "Переконайтеся, що:\n"
                "• Зображення чітке та добре освітлене\n"
                "• QR код видно на фото\n"
                "• Фото не розмите\n\n"
                "Спробуйте зробити фото ще раз або надішліть чек вручну."
            )
        elif error_type == "scraping_error":
            message = (
                "❌ <b>Не вдалося отримати позиції з чека</b>\n\n"
                "На жаль, не вдалося отримати інформацію про товари з сайту податкової служби.\n\n"
                "Можливі причини:\n"
                "• Сайт тимчасово недоступний\n"
                "• Чек не знайдено в системі\n"
                "• Помилка при обробці даних\n\n"
                "Спробуйте надіслати чек ще раз пізніше або введіть дані вручну."
            )
        else:
            message = (
                "❌ <b>Помилка обробки чека</b>\n\n"
                "На жаль, сталася помилка при обробці вашого чека.\n\n"
                "Будь ласка, спробуйте надіслати чек ще раз або зверніться до підтримки."
            )
        
        success = await notifier.send_message(telegram_id, message)
        if success:
            LOGGER.info("Successfully sent error notification to user %s for receipt %s (error_type=%s)", telegram_id, receipt_id, error_type)
        else:
            LOGGER.warning("Failed to send error notification to user %s for receipt %s (error_type=%s)", telegram_id, receipt_id, error_type)
    except Exception as e:
        LOGGER.error(
            "Exception while sending error notification to user %s for receipt %s: %s",
            telegram_id,
            receipt_id,
            e,
            exc_info=True,
        )
    finally:
        await notifier.close()

