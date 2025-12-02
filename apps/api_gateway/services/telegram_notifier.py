from __future__ import annotations

import logging
from typing import Any

import httpx

from libs.common import AppSettings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Service for sending notifications to users via Telegram Bot API."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def send_message(
        self,
        telegram_id: int,
        text: str,
        parse_mode: str | None = "HTML",
    ) -> bool:
        """
        Send a message to a user via Telegram Bot API.
        
        Args:
            telegram_id: Telegram user ID
            text: Message text
            parse_mode: Parse mode for message formatting (default: HTML)
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            payload: dict[str, Any] = {
                "chat_id": telegram_id,
                "text": text,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode

            response = await self._client.post(
                f"{self.base_url}/sendMessage",
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"Successfully sent Telegram message to user {telegram_id}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to send Telegram message to user {telegram_id}: "
                f"HTTP {e.response.status_code}: {e.response.text}"
            )
            return False
        except httpx.RequestError as e:
            logger.error(
                f"Request error while sending Telegram message to user {telegram_id}: {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error while sending Telegram message to user {telegram_id}: {e}",
                exc_info=True,
            )
            return False

    async def notify_payout_success(
        self,
        telegram_id: int,
        amount: float,
        phone_number: str | None = None,
    ) -> bool:
        """
        Notify user about successful payout.
        
        Args:
            telegram_id: Telegram user ID
            amount: Payout amount in UAH
            phone_number: Phone number (optional, for display)
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        phone_display = phone_number if phone_number else "ваш номер"
        text = (
            f"✅ <b>Виплата успішна!</b>\n\n"
            f"На ваш мобільний телефон {phone_display} було зараховано {amount:.2f} ₴.\n\n"
            f"Дякуємо за покупку продукції Дарниця!"
        )
        return await self.send_message(telegram_id, text)

    async def notify_payout_failed(
        self,
        telegram_id: int,
        error_description: str | None = None,
    ) -> bool:
        """
        Notify user about failed payout.
        
        Args:
            telegram_id: Telegram user ID
            error_description: Error description (optional)
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        error_msg = f"\n\nПричина: {error_description}" if error_description else ""
        text = (
            f"❌ <b>Помилка виплати</b>\n\n"
            f"На жаль, не вдалося виконати виплату бонусу.{error_msg}\n\n"
            f"Будь ласка, зверніться до підтримки або спробуйте надіслати чек ще раз."
        )
        return await self.send_message(telegram_id, text)

    async def notify_phone_required(
        self,
        telegram_id: int,
    ) -> bool:
        """
        Notify user that phone number is required for payout.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        text = (
            f"⚠️ <b>Потрібен номер телефону</b>\n\n"
            f"Для виплати бонусу нам потрібен ваш номер телефону.\n\n"
            f"Будь ласка, надішліть номер телефону через команду /change_phone або кнопку меню."
        )
        return await self.send_message(telegram_id, text)

