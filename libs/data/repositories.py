from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import BonusTransaction, CatalogItem, LineItem, Receipt, User
from libs.common.crypto import Encryptor
import hashlib


class UserRepository:
    def __init__(self, session: AsyncSession, encryptor: Encryptor | None = None) -> None:
        self.session = session
        self.encryptor = encryptor or Encryptor()

    async def upsert_user(
        self, telegram_id: int, phone_number: str | None, locale: str
    ) -> User:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        encrypted, hashed = self._transform_phone(phone_number)
        if user:
            user.phone_number = encrypted or user.phone_number
            user.phone_hash = hashed or user.phone_hash
            user.locale = locale
        else:
            user = User(
                telegram_id=telegram_id,
                phone_number=encrypted,
                phone_hash=hashed,
                locale=locale,
            )
            self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_telegram(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def decrypt_phone(self, user: User) -> str | None:
        if not user.phone_number:
            return None
        return self.encryptor.decrypt(user.phone_number)

    def _transform_phone(self, phone_number: str | None) -> tuple[str | None, str | None]:
        if not phone_number:
            return None, None
        encrypted = self.encryptor.encrypt(phone_number)
        hashed = hashlib.sha256(phone_number.encode("utf-8")).hexdigest()
        return encrypted, hashed


class ReceiptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_receipt(
        self,
        *,
        user_id: UUID,
        upload_ts: datetime,
        storage_object_key: str,
        checksum: str,
    ) -> Receipt:
        receipt = Receipt(
            user_id=user_id,
            upload_ts=upload_ts,
            storage_object_key=storage_object_key,
            checksum=checksum,
            status="pending",
        )
        self.session.add(receipt)
        await self.session.flush()
        return receipt

    async def history_for_user(self, user_id: UUID, limit: int = 5) -> Sequence[Receipt]:
        stmt = (
            select(Receipt)
            .options(selectinload(Receipt.bonus_transaction))
            .where(Receipt.user_id == user_id)
            .order_by(Receipt.upload_ts.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def receipts_last_days(self, user_id: UUID, days: int) -> Sequence[Receipt]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = select(Receipt).where(Receipt.user_id == user_id, Receipt.upload_ts >= since)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def daily_submission_count(self, user_id: UUID) -> int:
        today = datetime.now(timezone.utc).date()
        stmt = (
            select(func.count(Receipt.id))
            .where(Receipt.user_id == user_id)
            .where(func.date(Receipt.upload_ts) == today)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> Sequence[CatalogItem]:
        stmt = select(CatalogItem).where(CatalogItem.active_flag.is_(True))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def upsert(self, sku_code: str, aliases: list[str]) -> CatalogItem:
        stmt: Select[CatalogItem] = select(CatalogItem).where(CatalogItem.sku_code == sku_code)
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()
        if item:
            item.product_aliases = aliases
        else:
            item = CatalogItem(sku_code=sku_code, product_aliases=aliases)
            self.session.add(item)
        await self.session.flush()
        return item


class BonusRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_bonus(
        self, *, receipt_id: UUID, user_id: UUID, msisdn: str, amount: int
    ) -> BonusTransaction:
        bonus = BonusTransaction(
            receipt_id=receipt_id, user_id=user_id, msisdn=msisdn, amount=amount
        )
        self.session.add(bonus)
        await self.session.flush()
        return bonus

