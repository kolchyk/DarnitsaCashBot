from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
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
    easypay_status: Mapped[str] = mapped_column(String(32), default=BonusStatus.CREATED)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    easypay_reference: Mapped[str | None] = mapped_column(String(64))

    receipt: Mapped["Receipt"] = relationship(back_populates="bonus_transaction")
    user: Mapped["User"] = relationship(back_populates="bonuses")

