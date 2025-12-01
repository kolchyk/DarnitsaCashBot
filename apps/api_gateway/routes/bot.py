from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.analytics import AnalyticsClient
from libs.common.messaging import MessageBroker, QueueNames
from libs.common.rate_limit import RateLimiter
from libs.common.storage import StorageClient
from libs.data.repositories import ReceiptRepository, UserRepository

from ..dependencies import (
    get_analytics,
    get_broker,
    get_receipt_rate_limiter,
    get_session_dep,
    get_storage_client,
)
from ..schemas import (
    ReceiptHistoryItem,
    ReceiptResponse,
    ReceiptUploadResponse,
    UserResponse,
    UserUpsertRequest,
)

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024
SUPPORTED_CONTENT_TYPES = {"image/jpeg", "image/png"}


@router.post("/users", response_model=UserResponse)
async def upsert_user(
    payload: UserUpsertRequest,
    session: AsyncSession = Depends(get_session_dep),
):
    user_repo = UserRepository(session)
    user = await user_repo.upsert_user(
        telegram_id=payload.telegram_id,
        phone_number=payload.phone_number,
        locale=payload.locale,
    )
    await session.commit()
    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        locale=user.locale,
        has_phone=bool(user.phone_number),
    )


@router.post("/receipts", response_model=ReceiptUploadResponse)
async def upload_receipt(
    telegram_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session_dep),
    storage: StorageClient = Depends(get_storage_client),
    broker: MessageBroker = Depends(get_broker),
    analytics: AnalyticsClient = Depends(get_analytics),
    limiter: RateLimiter = Depends(get_receipt_rate_limiter),
):
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if file.content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 10MB limit")

    allowed = await limiter.check(str(telegram_id))
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many uploads. Please wait a minute.")

    checksum = hashlib.sha256(data).hexdigest()
    object_key = f"receipts/{user.id}/{uuid4()}.{file.filename.split('.')[-1]}"
    await storage.upload_bytes(key=object_key, content=data, content_type=file.content_type or "image/jpeg")

    receipt_repo = ReceiptRepository(session)
    receipt = await receipt_repo.create_receipt(
        user_id=user.id,
        upload_ts=datetime.now(timezone.utc),
        storage_object_key=object_key,
        checksum=checksum,
    )
    await session.commit()

    payload = {
        "receipt_id": str(receipt.id),
        "user_id": str(user.id),
        "storage_key": object_key,
        "checksum": checksum,
        "telegram_id": telegram_id,
    }
    await broker.publish(QueueNames.RECEIPTS, payload)
    await analytics.record("receipt_uploaded", payload)
    return ReceiptUploadResponse(
        receipt=ReceiptResponse(receipt_id=receipt.id, status=receipt.status),
        queue_reference=QueueNames.RECEIPTS,
    )


@router.get("/history/{telegram_id}", response_model=list[ReceiptHistoryItem])
async def get_history(
    telegram_id: int,
    session: AsyncSession = Depends(get_session_dep),
):
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    receipt_repo = ReceiptRepository(session)
    receipts = await receipt_repo.history_for_user(user.id)
    history: list[ReceiptHistoryItem] = []
    for receipt in receipts:
        bonus = receipt.bonus_transaction
        history.append(
            ReceiptHistoryItem(
                receipt_id=receipt.id,
                status=receipt.status,
                uploaded_at=receipt.upload_ts,
                payout_reference=bonus.portmone_bill_id if bonus else None,
                payout_status=bonus.payout_status if bonus else None,
            )
        )
    return history

