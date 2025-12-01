from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common import AppSettings
from libs.common.analytics import AnalyticsClient
from libs.common.messaging import MessageBroker, QueueNames
from libs.common.portmone import PortmoneResponse, parse_portmone_response
from libs.common.xml_utils import XMLParseError
from libs.data.models import BonusStatus, BonusTransaction, Receipt, ReceiptStatus

from ..dependencies import (
    get_analytics,
    get_broker,
    get_session_dep,
    get_settings_dep,
)

router = APIRouter()


@router.post("/webhook")
async def portmone_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session_dep),
    broker: MessageBroker = Depends(get_broker),
    analytics: AnalyticsClient = Depends(get_analytics),
    settings: AppSettings = Depends(get_settings_dep),
) -> dict[str, str]:
    if settings.portmone_webhook_token:
        provided = request.headers.get("x-portmone-token")
        if provided != settings.portmone_webhook_token:
            raise HTTPException(status_code=401, detail="Invalid Portmone webhook token")

    body = await request.body()
    try:
        response = parse_portmone_response(body.decode("utf-8"))
    except XMLParseError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid XML: {exc}") from exc

    bill_id = response.bill_id
    if not bill_id:
        raise HTTPException(status_code=400, detail="Missing bill identifier")

    stmt = select(BonusTransaction).where(BonusTransaction.portmone_bill_id == bill_id)
    bonus: BonusTransaction | None = await session.scalar(stmt)
    if not bonus:
        raise HTTPException(status_code=404, detail="Bonus transaction not found")

    receipt: Receipt | None = await session.get(Receipt, bonus.receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    await session.refresh(receipt, attribute_names=["user"])

    await _apply_callback(session, bonus, receipt, response)

    telegram_id = receipt.user.telegram_id if receipt.user else None
    event_status = ReceiptStatus.PAYOUT_SUCCESS if response.status == "ok" else ReceiptStatus.PAYOUT_FAILED

    await analytics.record(
        "payout_success" if response.status == "ok" else "payout_failure",
        {
            "receipt_id": str(receipt.id),
            "bonus_id": str(bonus.id),
            "bill_id": bill_id,
        },
    )
    await broker.publish(
        QueueNames.BONUS_EVENTS,
        {
            "receipt_id": str(receipt.id),
            "transaction_id": str(bonus.id),
            "status": event_status,
            "payout_status": bonus.payout_status,
            "bill_id": bonus.portmone_bill_id,
            "telegram_id": telegram_id,
            "error_code": bonus.portmone_error_code,
            "error_description": bonus.portmone_error_description,
        },
    )
    return {"status": "ok"}


async def _apply_callback(
    session: AsyncSession,
    bonus: BonusTransaction,
    receipt: Receipt,
    response: PortmoneResponse,
) -> None:
    if response.bill_id and not bonus.portmone_bill_id:
        bonus.portmone_bill_id = response.bill_id
    bonus.portmone_status = response.status
    bonus.callback_payload = response.data

    if response.status == "ok":
        bonus.payout_status = BonusStatus.SUCCESS
        bonus.portmone_error_code = None
        bonus.portmone_error_description = None
        receipt.status = ReceiptStatus.PAYOUT_SUCCESS
    else:
        bonus.payout_status = BonusStatus.FAILED
        first_error = response.errors[0] if response.errors else None
        bonus.portmone_error_code = first_error.code if first_error else bonus.portmone_error_code
        # prefer description, then message for user-friendly reason
        description = None
        if first_error:
            description = first_error.description or first_error.message
        bonus.portmone_error_description = description or bonus.portmone_error_description
        receipt.status = ReceiptStatus.PAYOUT_FAILED

    await session.commit()

