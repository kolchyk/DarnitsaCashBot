from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.data.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReceiptStatus(str):
    PENDING = "pending"
    PROCESSING = "processing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PAYOUT_PENDING = "payout_pending"
    PAYOUT_SUCCESS = "payout_success"
    PAYOUT_FAILED = "payout_failed"


class Receipt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "receipts"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    upload_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    purchase_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merchant: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default=ReceiptStatus.PENDING)
    ocr_payload: Mapped[dict | None] = mapped_column(JSON)
    storage_object_key: Mapped[str] = mapped_column(String(256))
    checksum: Mapped[str] = mapped_column(String(128))

    user: Mapped["User"] = relationship(back_populates="receipts")
    line_items: Mapped[list["LineItem"]] = relationship(back_populates="receipt")
    bonus_transaction: Mapped["BonusTransaction | None"] = relationship(back_populates="receipt")


class LineItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "line_items"

    receipt_id: Mapped[UUID] = mapped_column(ForeignKey("receipts.id"), index=True)
    sku_code: Mapped[str | None] = mapped_column(String(64))
    product_name: Mapped[str] = mapped_column(String(256))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[int] = mapped_column(BigInteger)  # store in kopecks to avoid float issues
    total_price: Mapped[int] = mapped_column(BigInteger)
    confidence: Mapped[float] = mapped_column(default=0.0)

    receipt: Mapped["Receipt"] = relationship(back_populates="line_items")

