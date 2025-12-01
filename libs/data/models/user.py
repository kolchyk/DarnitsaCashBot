from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.data.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger(), unique=True, index=True)
    phone_number: Mapped[str | None] = mapped_column(String(256))
    phone_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    locale: Mapped[str] = mapped_column(String(5), default="uk")
    consent_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    receipts: Mapped[list["Receipt"]] = relationship(back_populates="user")
    bonuses: Mapped[list["BonusTransaction"]] = relationship(back_populates="user")

