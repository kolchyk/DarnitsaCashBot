from __future__ import annotations

from typing import Any

import httpx


class ReceiptApiClient:
    """HTTP client for interacting with the API gateway."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url)

    async def close(self) -> None:
        await self._client.aclose()

    async def register_user(
        self, *, telegram_id: int, phone_number: str | None, locale: str
    ) -> dict[str, Any]:
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

    async def upload_receipt(
        self,
        *,
        telegram_id: int,
        photo_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> dict[str, Any]:
        files = {"file": (filename, photo_bytes, content_type)}
        response = await self._client.post("/bot/receipts", params={"telegram_id": telegram_id}, files=files)
        response.raise_for_status()
        return response.json()

    async def fetch_history(self, *, telegram_id: int) -> list[dict[str, Any]]:
        response = await self._client.get(f"/bot/history/{telegram_id}")
        response.raise_for_status()
        return response.json()

