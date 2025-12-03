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
from .receipt_scraper import scrape_receipt_data_via_selenium, ScrapingError
# API imports reserved for future use as fallback
# from .tax_api_client import TaxApiError, fetch_receipt_data, parse_receipt_url

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
            
            # Step 2: Fetch receipt data using Selenium (browser automation)
            scraped_data = {
                "merchant": None,
                "purchase_ts": None,
                "total": None,
                "line_items": [],
                "confidence": {
                    "mean": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "token_count": 0,
                    "auto_accept_candidate": False,
                },
                "manual_review_required": True,
                "anomalies": [],
            }
            
            # Fetch data using Selenium if URL is valid
            if qr_url and qr_url.startswith(("http://", "https://")):
                try:
                    LOGGER.info(
                        "Fetching receipt data using Selenium for receipt %s: url=%s",
                        receipt_id,
                        qr_url,
                    )
                    
                    # Fetch receipt data using Selenium (runs in thread pool as it's synchronous)
                    selenium_data = await asyncio.to_thread(scrape_receipt_data_via_selenium, qr_url)
                    
                    LOGGER.info(
                        "Received Selenium data for receipt %s: merchant=%s, line_items=%d, total=%s",
                        receipt_id,
                        selenium_data.get("merchant"),
                        len(selenium_data.get("line_items", [])),
                        selenium_data.get("total"),
                    )
                    
                    # Merge Selenium data into scraped_data
                    scraped_data.update(selenium_data)
                    
                except ScrapingError as e:
                    LOGGER.warning("Failed to fetch receipt data using Selenium for receipt %s: %s", receipt_id, e)
                    scraped_data["anomalies"].append(f"Selenium scraping error: {str(e)}")
                    # Notify user about scraping error
                    if telegram_id:
                        await _notify_scraping_error(telegram_id, receipt_id, e)
                except Exception as e:
                    LOGGER.error(
                        "Unexpected error while fetching receipt data using Selenium for receipt %s: %s",
                        receipt_id,
                        e,
                        exc_info=True,
                    )
                    scraped_data["anomalies"].append(f"Unexpected error fetching receipt data: {str(e)}")
            else:
                LOGGER.warning("Invalid QR URL format for receipt %s: %s", receipt_id, qr_url)
                scraped_data["anomalies"].append("Invalid QR URL format")
            
            # API method reserved as fallback (currently not used)
            # Uncomment below code if you want to use API as fallback when Selenium fails
            # 
            # if not scraped_data.get("line_items") and qr_url and qr_url.startswith(("http://", "https://")) and settings.tax_gov_ua_api_token:
            #     try:
            #         from .tax_api_client import TaxApiError, fetch_receipt_data, parse_receipt_url
            #         url_params = parse_receipt_url(qr_url)
            #         receipt_api_id = url_params.get("id")
            #         if receipt_api_id:
            #             LOGGER.info("Falling back to API for receipt %s", receipt_id)
            #             api_response = await fetch_receipt_data(
            #                 receipt_id=receipt_api_id,
            #                 token=settings.tax_gov_ua_api_token,
            #                 date=url_params.get("date"),
            #                 fn=url_params.get("fn"),
            #                 receipt_type=3,
            #             )
            #             # Process API response...
            #     except Exception as e:
            #         LOGGER.warning("API fallback also failed: %s", e)
            
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


async def _notify_api_response(telegram_id: int, receipt_id: UUID, api_response: dict[str, Any]) -> None:
    """
    Send API response from tax.gov.ua to user via Telegram.
    
    NOTE: This function is reserved for future use when API method is enabled as fallback.
    Currently not used as we're using Selenium only.
    """
    LOGGER.info("Attempting to send API response to user %s for receipt %s", telegram_id, receipt_id)
    
    settings = get_settings()
    from apps.api_gateway.services.telegram_notifier import TelegramNotifier
    
    notifier = TelegramNotifier(settings)
    try:
        # Build message with API response data
        message_parts = ["✅ <b>Дані чека отримано з реєстру фіскальних чеків</b>\n\n"]
        message_parts.append("━━━━━━━━━━━━━━━━━━━━\n\n")
        
        # Add merchant name if available (most important info first)
        merchant_name = api_response.get("name")
        if merchant_name:
            message_parts.append(f"🏪 <b>Торговельна точка:</b> {merchant_name}\n\n")
        
        # Add receipt ID if available
        receipt_api_id = api_response.get("id")
        if receipt_api_id:
            message_parts.append(f"🆔 <b>Номер чека:</b> {receipt_api_id}\n\n")
        
        # Add fiscal number if available
        fn_value = api_response.get("fn")
        if fn_value:
            message_parts.append(f"📋 <b>Фіскальний номер РРО:</b> {fn_value}\n\n")
        
        message_parts.append("━━━━━━━━━━━━━━━━━━━━\n\n")
        
        # Add check data (text receipt) if available
        check_data = api_response.get("check")
        if check_data and isinstance(check_data, str):
            message_parts.append("📄 <b>Дані чека:</b>\n")
            message_parts.append("<pre>")
            # Calculate available space (Telegram limit is 4096 characters, reserve ~500 for other content)
            available_space = 3500
            # Count current message length
            current_length = len("".join(message_parts))
            remaining_space = available_space - current_length
            
            if remaining_space > 100:
                # Escape HTML special characters in check data for <pre> tag
                check_preview = check_data[:remaining_space - 50] if len(check_data) > remaining_space - 50 else check_data
                # Replace HTML entities that might break the message
                check_preview = check_preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                message_parts.append(check_preview)
                if len(check_data) > remaining_space - 50:
                    message_parts.append("\n\n... (текст обрізано через обмеження Telegram)")
            else:
                message_parts.append("(текст чека занадто великий для відображення)")
            
            message_parts.append("</pre>\n\n")
        
        # Add additional info section
        has_additional_info = False
        info_parts = []
        
        # Add XML availability info
        xml_value = api_response.get("xml")
        if xml_value:
            if isinstance(xml_value, bool) and xml_value:
                info_parts.append("✅ XML дані доступні")
                has_additional_info = True
            elif isinstance(xml_value, str) and xml_value:
                info_parts.append("✅ XML дані доступні")
                has_additional_info = True
        
        # Add signature info
        sign_value = api_response.get("sign")
        if sign_value:
            if isinstance(sign_value, bool) and sign_value:
                info_parts.append("✅ Чек підписано КЕП")
                has_additional_info = True
            elif isinstance(sign_value, str) and sign_value:
                info_parts.append("✅ Чек підписано КЕП")
                has_additional_info = True
        
        if has_additional_info:
            message_parts.append("📌 <b>Додаткова інформація:</b>\n")
            message_parts.append("\n".join(info_parts))
            message_parts.append("\n\n")
        
        message = "".join(message_parts)
        
        # Ensure message doesn't exceed Telegram limit
        if len(message) > 4096:
            # Truncate message and add note
            message = message[:4000] + "\n\n... (повідомлення обрізано)"
        
        success = await notifier.send_message(telegram_id, message)
        if success:
            LOGGER.info("Successfully sent API response to user %s for receipt %s", telegram_id, receipt_id)
        else:
            LOGGER.warning("Failed to send API response to user %s for receipt %s", telegram_id, receipt_id)
    except Exception as e:
        LOGGER.error(
            "Exception while sending API response to user %s for receipt %s: %s",
            telegram_id,
            receipt_id,
            e,
            exc_info=True,
        )
    finally:
        await notifier.close()


async def _notify_api_error(telegram_id: int, receipt_id: UUID, api_error: Any) -> None:
    """
    Send API error notification to user via Telegram.
    
    NOTE: This function is reserved for future use when API method is enabled as fallback.
    Currently not used as we're using Selenium only.
    """
    # Import TaxApiError only when needed (for future use)
    from .tax_api_client import TaxApiError
    
    LOGGER.info("Attempting to send API error notification to user %s for receipt %s", telegram_id, receipt_id)
    
    settings = get_settings()
    from apps.api_gateway.services.telegram_notifier import TelegramNotifier
    
    notifier = TelegramNotifier(settings)
    try:
        # Build error message
        message_parts = ["⚠️ <b>Помилка отримання даних з реєстру фіскальних чеків</b>\n\n"]
        
        # Get error description if available
        error_description = getattr(api_error, 'error_description', None) or str(api_error)
        status_code = getattr(api_error, 'status_code', None)
        
        if status_code == 400:
            # Check if it's a wartime restriction
            if "воєнн" in error_description.lower() or "обмежено доступ" in error_description.lower():
                message_parts.append(
                    "На період дії воєнного стану обмежено доступ до публічних електронних реєстрів.\n\n"
                    "💡 <b>Що це означає?</b>\n"
                    "Чек успішно розпізнано, але отримати детальні дані з реєстру зараз неможливо через обмеження.\n\n"
                    "✅ Ваш чек все одно буде оброблено та перевірено на наявність продуктів Дарниця."
                )
            else:
                message_parts.append(
                    f"Не вдалося отримати дані чека з реєстру.\n\n"
                    f"<b>Деталі помилки:</b> {error_description}\n\n"
                    f"✅ Ваш чек все одно буде оброблено та перевірено на наявність продуктів Дарниця."
                )
        elif status_code == 401:
            message_parts.append(
                "Помилка авторизації при доступі до реєстру фіскальних чеків.\n\n"
                "✅ Ваш чек все одно буде оброблено та перевірено на наявність продуктів Дарниця."
            )
        elif status_code == 404:
            message_parts.append(
                "Чек не знайдено в реєстрі фіскальних чеків.\n\n"
                "💡 <b>Можливі причини:</b>\n"
                "• Чек ще не зареєстровано в системі\n"
                "• Неправильні дані в QR коді\n\n"
                "✅ Ваш чек все одно буде оброблено та перевірено на наявність продуктів Дарниця."
            )
        else:
            message_parts.append(
                f"Сталася помилка при отриманні даних з реєстру фіскальних чеків.\n\n"
                f"<b>Деталі:</b> {error_description}\n\n"
                f"✅ Ваш чек все одно буде оброблено та перевірено на наявність продуктів Дарниця."
            )
        
        message = "".join(message_parts)
        
        success = await notifier.send_message(telegram_id, message)
        if success:
            LOGGER.info("Successfully sent API error notification to user %s for receipt %s", telegram_id, receipt_id)
        else:
            LOGGER.warning("Failed to send API error notification to user %s for receipt %s", telegram_id, receipt_id)
    except Exception as e:
        LOGGER.error(
            "Exception while sending API error notification to user %s for receipt %s: %s",
            telegram_id,
            receipt_id,
            e,
            exc_info=True,
        )
    finally:
        await notifier.close()


async def _notify_scraping_error(telegram_id: int, receipt_id: UUID, scraping_error: ScrapingError) -> None:
    """Send scraping error notification to user via Telegram."""
    LOGGER.info("Attempting to send scraping error notification to user %s for receipt %s", telegram_id, receipt_id)
    
    settings = get_settings()
    from apps.api_gateway.services.telegram_notifier import TelegramNotifier
    import html
    
    notifier = TelegramNotifier(settings)
    try:
        # Build error message
        message_parts = ["⚠️ <b>Помилка отримання даних з реєстру фіскальних чеків</b>\n\n"]
        
        # Escape HTML entities in error description to prevent parsing errors
        error_description = html.escape(str(scraping_error))
        # Truncate very long error messages to avoid Telegram message limits
        if len(error_description) > 500:
            error_description = error_description[:497] + "..."
        
        message_parts.append(
            "Не вдалося отримати дані чека з сайту податкової служби через браузерну автоматизацію.\n\n"
            f"<b>Деталі помилки:</b> {error_description}\n\n"
            "💡 <b>Можливі причини:</b>\n"
            "• Сайт тимчасово недоступний\n"
            "• Чек не знайдено в системі\n"
            "• Помилка при обробці даних\n\n"
            "✅ Ваш чек все одно буде оброблено та перевірено на наявність продуктів Дарниця."
        )
        
        message = "".join(message_parts)
        
        success = await notifier.send_message(telegram_id, message)
        if success:
            LOGGER.info("Successfully sent scraping error notification to user %s for receipt %s", telegram_id, receipt_id)
        else:
            LOGGER.warning("Failed to send scraping error notification to user %s for receipt %s", telegram_id, receipt_id)
    except Exception as e:
        LOGGER.error(
            "Exception while sending scraping error notification to user %s for receipt %s: %s",
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

