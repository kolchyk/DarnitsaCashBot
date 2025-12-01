import httpx
import pytest

from libs.common.config import AppSettings
from libs.common.portmone import PortmoneDirectClient, PortmoneResponseError


def _settings() -> AppSettings:
    return AppSettings(
        telegram_bot_token="test-token",
        encryption_secret="test-encryption-secret",
        portmone_api_base="https://mock/",
    )


@pytest.mark.asyncio
async def test_portmone_client_success():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = '<rsp status="ok"><bill><billId>900</billId></bill></rsp>'
        return httpx.Response(200, text=body)

    transport = httpx.MockTransport(handler)
    mock_http = httpx.AsyncClient(transport=transport, base_url="https://mock/")
    client = PortmoneDirectClient(settings=_settings(), client=mock_http)

    response = await client.call("bills.create", payeeId="1", contractNumber="123", amount="1.00", currency="UAH")
    assert response.status == "ok"
    assert response.bill_id == "900"

    await mock_http.aclose()


@pytest.mark.asyncio
async def test_portmone_client_failure_raises():
    async def handler(request: httpx.Request) -> httpx.Response:
        body = '<rsp status="fail"><error code="400">bad</error></rsp>'
        return httpx.Response(200, text=body)

    transport = httpx.MockTransport(handler)
    mock_http = httpx.AsyncClient(transport=transport, base_url="https://mock/")
    client = PortmoneDirectClient(settings=_settings(), client=mock_http)

    with pytest.raises(PortmoneResponseError):
        await client.call("bills.create", payeeId="1", contractNumber="123", amount="1.00", currency="UAH")

    await mock_http.aclose()

