from __future__ import annotations

import csv
import io
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.data.models import LineItem, Receipt, User

from ..dependencies import get_session_dep
from ..security import service_key_guard

router = APIRouter(dependencies=[Depends(service_key_guard)])


@router.get("/receipts")
async def search_receipts(
    phone: str | None = None,
    telegram_id: int | None = None,
    session: AsyncSession = Depends(get_session_dep),
):
    stmt: Select[tuple[Receipt, User]] = select(Receipt, User).join(User, Receipt.user_id == User.id)
    if phone:
        stmt = stmt.where(User.phone_number == phone)
    if telegram_id:
        stmt = stmt.where(User.telegram_id == telegram_id)
    result = await session.execute(stmt.limit(50))
    data = [
        {
            "receipt_id": str(receipt.id),
            "status": receipt.status,
            "user_id": str(user.id),
            "telegram_id": user.telegram_id,
            "phone_number": user.phone_number,
            "upload_ts": receipt.upload_ts,
            "merchant": receipt.merchant,
        }
        for receipt, user in result.all()
    ]
    return data


@router.post("/receipts/{receipt_id}/override")
async def override_receipt(
    receipt_id: UUID,
    status: str,
    session: AsyncSession = Depends(get_session_dep),
):
    stmt = select(Receipt).where(Receipt.id == receipt_id)
    result = await session.execute(stmt)
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    receipt.status = status
    await session.commit()
    return {"receipt_id": str(receipt.id), "status": receipt.status}


@router.post("/receipts/{receipt_id}/replay-payout")
async def replay_payout(receipt_id: UUID):
    # Hook for future integration with bonus service queue.
    return {"receipt_id": str(receipt_id), "status": "queued"}


@router.get("/exports/bonuses")
async def export_bonuses(session: AsyncSession = Depends(get_session_dep)):
    stmt = (
        select(LineItem.product_name, LineItem.sku_code, LineItem.quantity)
        .join(Receipt, LineItem.receipt_id == Receipt.id)
        .where(Receipt.status == "accepted")
    )
    result = await session.execute(stmt)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["product_name", "sku_code", "quantity"])
    for row in result.all():
        writer.writerow(row)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bonuses.csv"},
    )

