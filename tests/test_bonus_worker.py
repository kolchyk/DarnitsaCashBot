from types import SimpleNamespace
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock

from libs.common.crypto import Encryptor
from libs.common.portmone import PortmoneErrorDetail, PortmoneResponse, PortmoneResponseError
from services.bonus_service import main as bonus_module


class _DummySettings(SimpleNamespace):
    pass


@pytest.mark.asyncio
async def test_trigger_payout_happy_path(monkeypatch):
    context = bonus_module.BonusContext(
        receipt_id=uuid4(),
        bonus_id=uuid4(),
        msisdn="380000000000",
        amount=100,
        payee_id="1",
        contract_number="380000000000",
        currency="UAH",
        telegram_id=123,
    )

    async def fake_prepare(*_args, **_kwargs):
        return context

    async def fake_pending(ctx, response, broker, analytics):
        fake_pending.called = True
        assert ctx == context
        assert response.bill_id == "42"

    fake_pending.called = False

    monkeypatch.setattr(bonus_module, "_prepare_bonus_context", fake_prepare)
    monkeypatch.setattr(bonus_module, "_record_pending", fake_pending)

    client = SimpleNamespace(
        call=AsyncMock(
            return_value=PortmoneResponse(
                status="ok",
                raw="<rsp></rsp>",
                data={"bill.billId": "42"},
                errors=[],
            )
        )
    )

    payload = {"status": "accepted", "receipt_id": str(context.receipt_id)}
    broker = SimpleNamespace()
    analytics = SimpleNamespace()

    await bonus_module.trigger_payout(
        payload=payload,
        broker=broker,
        analytics=analytics,
        client=client,
        encryptor=Encryptor(),
        settings=_DummySettings(portmone_payee_id="1", portmone_default_currency="UAH"),
    )

    client.call.assert_awaited()
    assert fake_pending.called


@pytest.mark.asyncio
async def test_trigger_payout_handles_response_error(monkeypatch):
    context = bonus_module.BonusContext(
        receipt_id=uuid4(),
        bonus_id=uuid4(),
        msisdn="380000000000",
        amount=100,
        payee_id="1",
        contract_number="380000000000",
        currency="UAH",
        telegram_id=123,
    )

    async def fake_prepare(*_args, **_kwargs):
        return context

    async def fake_failure(**_kwargs):
        fake_failure.called = True

    fake_failure.called = False

    monkeypatch.setattr(bonus_module, "_prepare_bonus_context", fake_prepare)
    monkeypatch.setattr(bonus_module, "_record_failure", fake_failure)

    response_error = PortmoneResponseError(
        PortmoneResponse(
            status="fail",
            raw="<rsp></rsp>",
            data={},
            errors=[PortmoneErrorDetail(code="400", message="bad")],
        )
    )

    async def failing_call(*_args, **_kwargs):
        raise response_error

    client = SimpleNamespace(call=AsyncMock(side_effect=failing_call))
    payload = {"status": "accepted", "receipt_id": str(context.receipt_id)}

    await bonus_module.trigger_payout(
        payload=payload,
        broker=SimpleNamespace(),
        analytics=SimpleNamespace(),
        client=client,
        encryptor=Encryptor(),
        settings=_DummySettings(portmone_payee_id="1", portmone_default_currency="UAH"),
    )

    assert fake_failure.called

