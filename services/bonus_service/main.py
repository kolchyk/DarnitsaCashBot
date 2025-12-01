from __future__ import annotations

import asyncio
import json
from uuid import UUID

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from libs.common import configure_logging, get_settings
from libs.common.analytics import AnalyticsClient
from libs.common.messaging import MessageBroker, QueueNames
from libs.common.crypto import Encryptor
from libs.data import async_session_factory
from libs.data.models import BonusStatus, BonusTransaction, Receipt, User


async def trigger_payout(payload: dict, broker: MessageBroker, analytics: AnalyticsClient) -> None:
    if payload.get("status") != "accepted":
        return
    settings = get_settings()
    receipt_id = UUID(payload["receipt_id"])
    encryptor = Encryptor()
    async with async_session_factory() as session:
        receipt: Receipt | None = await session.get(Receipt, receipt_id)
        if not receipt:
            return
        await session.refresh(receipt, attribute_names=["user"])
        user: User | None = receipt.user
        phone = encryptor.decrypt(user.phone_number) if user and user.phone_number else None
        if not phone:
            return
        bonus: BonusTransaction | None = receipt.bonus_transaction
        if not bonus:
            bonus = BonusTransaction(
                receipt_id=receipt.id,
                user_id=user.id,
                msisdn=phone,
                amount=100,
            )
            session.add(bonus)
        bonus.easypay_status = BonusStatus.IN_PROGRESS
        await session.commit()

    payload_for_api = {
        "msisdn": bonus.msisdn,
        "amount": bonus.amount,
        "reference": str(bonus.id),
        "receipt_id": str(receipt.id),
    }

    async def call_easypay():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.easypay_api_base}/topup",
                json={
                    "merchant_id": settings.easypay_merchant_id,
                    "merchant_secret": settings.easypay_merchant_secret,
                    **payload_for_api,
                },
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

    response_data = None
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
    ):
        with attempt:
            response_data = await call_easypay()

    async with async_session_factory() as session:
        bonus = await session.get(BonusTransaction, bonus.id)
        receipt = await session.get(Receipt, receipt_id)
        if not bonus or not receipt:
            return
        await session.refresh(receipt, attribute_names=["user"])
        if response_data and response_data.get("status") == "success":
            bonus.easypay_status = BonusStatus.SUCCESS
            bonus.easypay_reference = response_data.get("transaction_id")
            receipt.status = "payout_success"
            await analytics.record("payout_success", {"receipt_id": str(receipt.id), "transaction_id": bonus.easypay_reference})
        else:
            bonus.easypay_status = BonusStatus.FAILED
            receipt.status = "payout_failed"
            await analytics.record("payout_failure", {"receipt_id": str(receipt.id)})
        await session.commit()

    telegram_id = receipt.user.telegram_id if receipt.user else None
    await broker.publish(
        QueueNames.BONUS_EVENTS,
        {
            "receipt_id": str(receipt_id),
            "transaction_id": str(bonus.id),
            "status": bonus.easypay_status,
            "telegram_id": telegram_id,
        },
    )


async def worker_loop() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    broker = MessageBroker(settings)
    analytics = AnalyticsClient(settings)

    while True:
        async with broker.consume(QueueNames.RULE_DECISIONS) as queue:
            async with queue.iterator() as iterator:
                async for message in iterator:
                    async with message.process():
                        payload = json.loads(message.body.decode("utf-8"))
                        await trigger_payout(payload, broker, analytics)
        await asyncio.sleep(1)


def run_worker():
    asyncio.run(worker_loop())


def run():
    asyncio.run(worker_loop())


if __name__ == "__main__":
    asyncio.run(worker_loop())

