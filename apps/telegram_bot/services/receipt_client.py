from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ReceiptApiClient:
    """HTTP client for interacting with the API gateway."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=10.0,
        )
        # Longer timeout for file uploads (60 seconds)
        self._upload_client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=60.0,
        )

    async def close(self) -> None:
        await self._client.aclose()
        await self._upload_client.aclose()

    async def register_user(
        self, *, telegram_id: int, phone_number: str | None, locale: str
    ) -> dict[str, Any]:
        try:
            response = await self._client.post(
                "/bot/users",
                json={
                    "telegram_id": telegram_id,
                    "phone_number": phone_number,
                    "locale": locale,
                },
            )
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to API Gateway at {self.base_url}: {e}")
            raise ConnectionError(f"API Gateway недоступен по адресу {self.base_url}. Убедитесь, что API Gateway запущен.") from e
        except httpx.TimeoutException as e:
            logger.error(f"Timeout connecting to API Gateway: {e}")
            raise TimeoutError("Превышено время ожидания ответа от API Gateway.") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"API Gateway returned error status {e.response.status_code}: {e.response.text}")
            raise

    async def upload_receipt(
        self,
        *,
        telegram_id: int,
        photo_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> dict[str, Any]:
        files = {"file": (filename, photo_bytes, content_type)}
        try:
            response = await self._upload_client.post("/bot/receipts", params={"telegram_id": telegram_id}, files=files)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to API Gateway at {self.base_url}: {e}")
            raise ConnectionError(f"API Gateway недоступен по адресу {self.base_url}. Убедитесь, что API Gateway запущен.") from e
        except httpx.TimeoutException as e:
            logger.error(f"Timeout uploading receipt to API Gateway: {e}")
            raise TimeoutError("Превышено время ожидания при загрузке чека. Пожалуйста, попробуйте еще раз.") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"API Gateway returned error status {e.response.status_code}: {e.response.text}")
            raise

    async def fetch_history(self, *, telegram_id: int) -> list[dict[str, Any]]:
        response = await self._client.get(f"/bot/history/{telegram_id}")
        response.raise_for_status()
        return response.json()

    async def get_receipt_status(self, *, receipt_id: str) -> dict[str, Any]:
        response = await self._client.get(f"/bot/receipts/{receipt_id}")
        response.raise_for_status()
        return response.json()

    async def submit_manual_receipt_data(
        self, *, receipt_id: str, merchant: str | None, purchase_date: str | None, line_items: list[dict[str, Any]]
    ) -> dict[str, Any]:
        response = await self._client.post(
            f"/bot/receipts/{receipt_id}/manual",
            json={
                "merchant": merchant,
                "purchase_date": purchase_date,
                "line_items": line_items,
            },
        )
        response.raise_for_status()
        return response.json()

