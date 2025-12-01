from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.data.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BonusStatus(str):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class BonusTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bonus_transactions"

    receipt_id: Mapped[UUID] = mapped_column(ForeignKey("receipts.id"), unique=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    msisdn: Mapped[str] = mapped_column(String(32))
    amount: Mapped[int] = mapped_column(Integer, default=100)  # stored in kopecks (1₴)
    payout_status: Mapped[str] = mapped_column(String(32), default=BonusStatus.CREATED)
    provider: Mapped[str] = mapped_column(String(32), default="portmone")
    currency: Mapped[str] = mapped_column(String(8), default="UAH")
    retries: Mapped[int] = mapped_column(Integer, default=0)
    payee_id: Mapped[str | None] = mapped_column(String(64))
    contract_number: Mapped[str | None] = mapped_column(String(64))
    portmone_bill_id: Mapped[str | None] = mapped_column(String(64))
    portmone_status: Mapped[str | None] = mapped_column(String(32))
    portmone_error_code: Mapped[str | None] = mapped_column(String(32))
    portmone_error_description: Mapped[str | None] = mapped_column(String(255))
    callback_payload: Mapped[dict | None] = mapped_column(JSON)

    receipt: Mapped["Receipt"] = relationship(back_populates="bonus_transaction")
    user: Mapped["User"] = relationship(back_populates="bonuses")

