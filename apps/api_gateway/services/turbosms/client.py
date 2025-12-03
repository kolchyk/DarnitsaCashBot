from __future__ import annotations

import logging
from typing import Any

import httpx

from libs.common import AppSettings

logger = logging.getLogger(__name__)


def normalize_phone_number(phone: str) -> str:
    """
    Нормалізує номер телефону до формату 380XXXXXXXXX (12 цифр).
    
    Args:
        phone: Номер телефону в будь-якому форматі
        
    Returns:
        Нормалізований номер телефону у форматі 380XXXXXXXXX
    """
    # Видаляємо всі нецифрові символи
    phone_normalized = "".join(filter(str.isdigit, phone))
    
    # Якщо номер не починається з 380, додаємо префікс
    if not phone_normalized.startswith("380"):
        # Якщо номер починається з 0, замінюємо на 380
        if phone_normalized.startswith("0"):
            phone_normalized = "380" + phone_normalized[1:]
        # Якщо номер починається з 80, додаємо 3
        elif phone_normalized.startswith("80"):
            phone_normalized = "3" + phone_normalized
        # Якщо номер починається з 8, додаємо 380
        elif phone_normalized.startswith("8"):
            phone_normalized = "380" + phone_normalized[1:]
        else:
            # Якщо номер не в відомому форматі, додаємо 380
            phone_normalized = "380" + phone_normalized
    
    # Перевіряємо, що номер в правильному форматі (380XXXXXXXXX, 12 цифр)
    if not phone_normalized.startswith("380") or len(phone_normalized) != 12:
        # Якщо номер не в правильному форматі, повертаємо оригінальний
        logger.warning(f"Phone number {phone} could not be normalized properly, using original")
        return phone
    
    return phone_normalized


class TurboSmsClient:
    """Клієнт для надсилання SMS через TurboSMS API."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.base_url = "https://api.turbosms.ua"
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        """Закрити HTTP клієнт."""
        await self._client.aclose()

    async def send_sms(
        self,
        phone_number: str,
        message: str,
        sender: str | None = None,
    ) -> bool:
        """
        Надіслати SMS повідомлення через TurboSMS API.
        
        Args:
            phone_number: Номер телефону отримувача
            message: Текст SMS повідомлення
            sender: Ім'я відправника (опціонально, використовується налаштування з конфігу якщо не вказано)
            
        Returns:
            True якщо SMS успішно надіслано, False інакше
        """
        # Перевіряємо, чи увімкнено TurboSMS
        if not self.settings.turbosms_enabled:
            logger.info("TurboSMS is disabled (turbosms_enabled=False), skipping SMS send")
            return False
        
        # Перевіряємо наявність токену
        if not self.settings.turbosms_token:
            logger.warning("TurboSMS token is not configured, cannot send SMS")
            return False
        
        # Нормалізуємо номер телефону
        normalized_phone = normalize_phone_number(phone_number)
        logger.info(f"Attempting to send SMS to {normalized_phone} via TurboSMS")
        
        # Використовуємо відправника з конфігу або переданого параметра
        sms_sender = sender or self.settings.turbosms_sender
        
        try:
            # Підготовка тіла запиту
            # Додаємо префікс "+" до номера телефону для міжнародного формату
            phone_with_prefix = f"+{normalized_phone}" if not normalized_phone.startswith("+") else normalized_phone
            payload: dict[str, Any] = {
                "recipients": [phone_with_prefix],
                "sms": {
                    "text": message,
                },
            }
            
            # Додаємо відправника якщо вказано
            if sms_sender:
                payload["sms"]["sender"] = sms_sender
            
            # Підготовка заголовків з аутентифікацією через Authorization header
            # (альтернативно можна використовувати GET параметр token)
            headers: dict[str, str] = {
                "Authorization": f"Bearer {self.settings.turbosms_token}",
            }
            
            # Відправляємо запит до TurboSMS API
            logger.debug(f"Sending SMS request to TurboSMS API: recipients={phone_with_prefix}, sender={sms_sender}, message_length={len(message)}")
            response = await self._client.post(
                f"{self.base_url}/message/send.json",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"TurboSMS API response: {result}")
            
            # Перевіряємо результат відповіді
            response_code = result.get("response_code", "")
            response_status = result.get("response_status", "")
            
            # TurboSMS API повертає різні коди успіху:
            # - response_code="0" або response_status="OK" для успіху
            # - response_status="SUCCESS_MESSAGE_SENT" також означає успіх
            if (
                response_code == "0" 
                or response_status == "OK" 
                or response_status == "SUCCESS_MESSAGE_SENT"
            ):
                logger.info(f"Successfully sent SMS to {normalized_phone}")
                return True
            else:
                logger.error(
                    f"Failed to send SMS to {normalized_phone}: "
                    f"response_code={response_code}, response_status={response_status}"
                )
                return False
                
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to send SMS to {normalized_phone}: "
                f"HTTP {e.response.status_code}: {e.response.text}"
            )
            return False
        except httpx.RequestError as e:
            logger.error(
                f"Request error while sending SMS to {normalized_phone}: {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error while sending SMS to {normalized_phone}: {e}",
                exc_info=True,
            )
            return False

