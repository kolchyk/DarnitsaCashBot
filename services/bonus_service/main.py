from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from libs.common import AppSettings, configure_logging, get_settings
from libs.common.analytics import AnalyticsClient
from libs.common.crypto import Encryptor
from libs.common.portmone import (
    PortmoneDirectClient,
    PortmoneResponse,
    PortmoneResponseError,
    PortmoneTransportError,
)
from libs.data import async_session_factory
from libs.data.models import BonusStatus, BonusTransaction, Receipt, ReceiptStatus, User

MAX_SUCCESSFUL_PAYOUTS_PER_DAY = 10


@dataclass
class BonusContext:
    receipt_id: UUID
    bonus_id: UUID
    msisdn: str
    amount: int
    payee_id: str
    contract_number: str
    currency: str
    telegram_id: int | None


async def trigger_payout(
    payload: dict,
    analytics: AnalyticsClient,
    client: PortmoneDirectClient,
    encryptor: Encryptor,
    settings: AppSettings,
) -> None:
    if payload.get("status") != ReceiptStatus.ACCEPTED:
        return

    receipt_id = UUID(payload["receipt_id"])
    context = await _prepare_bonus_context(receipt_id, encryptor, settings)
    if not context:
        return

    portmone_payload = {
        "payeeId": context.payee_id,
        "contractNumber": context.contract_number,
        "amount": f"{context.amount / 100:.2f}",
        "currency": context.currency,
        "comment": f"Top-up for receipt {context.receipt_id}",
    }

    response: PortmoneResponse | None = None
    try:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(PortmoneTransportError),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            stop=stop_after_attempt(3),
        ):
            with attempt:
                response = await client.call("bills.create", **portmone_payload)
    except PortmoneResponseError as exc:
        await _record_failure(
            context=context,
            analytics=analytics,
            error_code=exc.response.errors[0].code if exc.response.errors else None,
            error_description=exc.response.errors[0].description if exc.response.errors else None,
            portmone_status=exc.response.status,
            payload_snapshot=exc.response.data,
        )
        return
    except PortmoneTransportError as exc:
        await _record_failure(
            context=context,
            analytics=analytics,
            error_code="transport",
            error_description=str(exc),
            portmone_status="fail",
            payload_snapshot=None,
        )
        return

    if response is None:
        await _record_failure(
            context=context,
            analytics=analytics,
            error_code="unknown",
            error_description="Empty Portmone response",
            portmone_status="fail",
            payload_snapshot=None,
        )
        return

    await _record_pending(context, response, analytics)


async def _prepare_bonus_context(
    receipt_id: UUID,
    encryptor: Encryptor,
    settings: AppSettings,
) -> BonusContext | None:
    async with async_session_factory() as session:
        receipt: Receipt | None = await session.get(Receipt, receipt_id)
        if not receipt:
            return None
        await session.refresh(receipt, attribute_names=["user", "bonus_transaction"])
        user: User | None = receipt.user
        phone = encryptor.decrypt(user.phone_number) if user and user.phone_number else None
        if not phone:
            return None

        bonus: BonusTransaction | None = receipt.bonus_transaction
        
        # Проверяем общее количество успешных начислений за сегодня
        # Если уже достигнут лимит, не создаем новое начисление
        today = datetime.now(timezone.utc).date()
        successful_payouts_count_stmt = (
            select(func.count(BonusTransaction.id))
            .where(BonusTransaction.payout_status == BonusStatus.SUCCESS)
            .where(func.date(BonusTransaction.created_at) == today)
        )
        # Если бонус уже существует для этого чека и он успешен, исключаем его из подсчета
        if bonus and bonus.payout_status == BonusStatus.SUCCESS:
            successful_payouts_count_stmt = successful_payouts_count_stmt.where(BonusTransaction.id != bonus.id)
        
        successful_payouts_count_result = await session.execute(successful_payouts_count_stmt)
        successful_payouts_count = successful_payouts_count_result.scalar_one() or 0
        
        if successful_payouts_count >= MAX_SUCCESSFUL_PAYOUTS_PER_DAY:
            # Достигнут лимит успешных начислений на сегодня
            return None
        if not bonus:
            bonus = BonusTransaction(
                receipt_id=receipt.id,
                user_id=user.id,
                msisdn=phone,
                amount=100,
            )
            session.add(bonus)
            await session.flush()

        bonus.msisdn = phone
        bonus.provider = "portmone"
        bonus.payee_id = settings.portmone_payee_id
        bonus.contract_number = phone
        bonus.currency = settings.portmone_default_currency
        bonus.payout_status = BonusStatus.IN_PROGRESS
        bonus.portmone_status = "pending"
        receipt.status = ReceiptStatus.PAYOUT_PENDING
        await session.commit()

        return BonusContext(
            receipt_id=receipt.id,
            bonus_id=bonus.id,
            msisdn=phone,
            amount=bonus.amount,
            payee_id=bonus.payee_id or settings.portmone_payee_id,
            contract_number=bonus.contract_number or phone,
            currency=bonus.currency,
            telegram_id=user.telegram_id if user else None,
        )


async def _record_pending(
    context: BonusContext,
    response: PortmoneResponse,
    analytics: AnalyticsClient,
) -> None:
    async with async_session_factory() as session:
        bonus = await session.get(BonusTransaction, context.bonus_id)
        receipt = await session.get(Receipt, context.receipt_id)
        if not bonus or not receipt:
            return
        bonus.portmone_bill_id = response.bill_id
        bonus.callback_payload = response.data
        bonus.portmone_status = response.status
        bonus.payout_status = BonusStatus.IN_PROGRESS
        await session.commit()

    await analytics.record(
        "payout_initiated",
        {
            "receipt_id": str(context.receipt_id),
            "bonus_id": str(context.bonus_id),
            "bill_id": response.bill_id,
        },
    )
    # RabbitMQ removed - bonus events are now stored in database only


async def _record_failure(
    context: BonusContext,
    analytics: AnalyticsClient,
    error_code: str | None,
    error_description: str | None,
    portmone_status: str,
    payload_snapshot: dict[str, str] | None,
) -> None:
    async with async_session_factory() as session:
        bonus = await session.get(BonusTransaction, context.bonus_id)
        receipt = await session.get(Receipt, context.receipt_id)
        if not bonus or not receipt:
            return
        bonus.payout_status = BonusStatus.FAILED
        bonus.portmone_status = portmone_status
        bonus.portmone_error_code = error_code
        bonus.portmone_error_description = error_description
        if payload_snapshot:
            bonus.callback_payload = payload_snapshot
        receipt.status = ReceiptStatus.PAYOUT_FAILED
        await session.commit()

    await analytics.record(
        "payout_failure",
        {
            "receipt_id": str(context.receipt_id),
            "bonus_id": str(context.bonus_id),
            "error_code": error_code,
        },
    )
    # RabbitMQ removed - bonus events are now stored in database only


async def worker_loop() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    analytics = AnalyticsClient(settings)
    encryptor = Encryptor()
    client = PortmoneDirectClient(settings)

    try:
        # RabbitMQ removed - worker no longer consumes from queue
        # This worker should be called directly or via HTTP endpoint instead
        while True:
            await asyncio.sleep(60)  # Placeholder - no longer consuming from queue
    finally:
        await client.aclose()


def run_worker():
    asyncio.run(worker_loop())


def run():
    asyncio.run(worker_loop())


if __name__ == "__main__":
    asyncio.run(worker_loop())

