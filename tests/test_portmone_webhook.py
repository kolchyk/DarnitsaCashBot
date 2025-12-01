from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.api_gateway.routes.portmone import _apply_callback
from libs.common.portmone import PortmoneErrorDetail, PortmoneResponse
from libs.data.models import BonusStatus, BonusTransaction, Receipt, ReceiptStatus


class _DummySession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def _receipt() -> Receipt:
    receipt = Receipt(
        user_id=uuid4(),
        upload_ts=datetime.now(timezone.utc),
        storage_object_key="obj",
        checksum="chk",
    )
    receipt.id = uuid4()
    receipt.user = SimpleNamespace(telegram_id=123)
    return receipt


def _bonus(receipt_id) -> BonusTransaction:
    bonus = BonusTransaction(
        receipt_id=receipt_id,
        user_id=uuid4(),
        msisdn="380000000000",
        amount=100,
    )
    bonus.id = uuid4()
    return bonus


@pytest.mark.asyncio
async def test_apply_callback_sets_success():
    receipt = _receipt()
    bonus = _bonus(receipt.id)
    session = _DummySession()

    response = PortmoneResponse(
        status="ok",
        raw="<rsp status='ok'></rsp>",
        data={"bill.billId": "42"},
        errors=[],
    )

    await _apply_callback(session, bonus, receipt, response)

    assert bonus.payout_status == BonusStatus.SUCCESS
    assert receipt.status == ReceiptStatus.PAYOUT_SUCCESS
    assert bonus.portmone_bill_id == "42"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_apply_callback_sets_failure_reason():
    receipt = _receipt()
    bonus = _bonus(receipt.id)
    session = _DummySession()

    response = PortmoneResponse(
        status="fail",
        raw="<rsp status='fail'></rsp>",
        data={},
        errors=[PortmoneErrorDetail(code="123", message="oops", description="failure")],
    )

    await _apply_callback(session, bonus, receipt, response)

    assert bonus.payout_status == BonusStatus.FAILED
    assert receipt.status == ReceiptStatus.PAYOUT_FAILED
    assert bonus.portmone_error_code == "123"
    assert bonus.portmone_error_description == "failure"

