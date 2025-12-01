from __future__ import annotations

from datetime import datetime
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


class ReceiptResponse(BaseModel):
    receipt_id: UUID
    status: str


class ReceiptHistoryItem(BaseModel):
    receipt_id: UUID
    status: str
    uploaded_at: datetime
    payout_reference: str | None = None
    payout_status: str | None = None


class ReceiptUploadResponse(BaseModel):
    receipt: ReceiptResponse
    queue_reference: str

