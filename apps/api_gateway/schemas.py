from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class UserUpsertRequest(BaseModel):
    telegram_id: int
    phone_number: str | None = None
    locale: str = "uk"


class UserResponse(BaseModel):
    id: UUID
    telegram_id: int
    locale: str
    has_phone: bool


class DarnitsaProduct(BaseModel):
    name: str
    price: float  # Price in UAH (converted from kopecks)
    quantity: int


class ReceiptLineItem(BaseModel):
    name: str
    quantity: int
    price: float  # Price in UAH (converted from kopecks)


class ReceiptResponse(BaseModel):
    receipt_id: UUID
    status: str
    darnitsa_products: list[DarnitsaProduct] | None = None
    line_items: list[ReceiptLineItem] | None = None  # All items from receipt


class ReceiptHistoryItem(BaseModel):
    receipt_id: UUID
    status: str
    uploaded_at: datetime
    payout_reference: str | None = None
    payout_status: str | None = None


class ReceiptUploadResponse(BaseModel):
    receipt: ReceiptResponse
    queue_reference: str


class ManualReceiptDataRequest(BaseModel):
    merchant: str | None = None
    purchase_date: str | None = None  # ISO format date string
    line_items: list[dict[str, Any]]  # List of items with name, quantity, price


class StatisticsResponse(BaseModel):
    user_count: int
    receipt_count: int
    bonus_count: int

