from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    RECEIPT_UPLOADED = "receipt_uploaded"
    RECEIPT_ACCEPTED = "receipt_accepted"
    RECEIPT_REJECTED = "receipt_rejected"
    PAYOUT_SUCCESS = "payout_success"
    PAYOUT_FAILURE = "payout_failure"
    REMINDER_PENDING = "reminder_pending"


class BaseEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID | None = None
    type: EventType


class ReceiptEvent(BaseEvent):
    receipt_id: UUID
    user_id: UUID


class PayoutEvent(BaseEvent):
    transaction_id: UUID
    receipt_id: UUID
    user_id: UUID
    amount: int

