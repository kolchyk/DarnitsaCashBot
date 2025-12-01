from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from libs.common import AppSettings, get_settings
from libs.common.xml_utils import XMLParseError, flatten_xml, parse_xml_document


@dataclass
class PortmoneErrorDetail:
    code: str | None
    message: str | None
    description: str | None = None


@dataclass
class PortmoneResponse:
    status: str
    raw: str
    data: dict[str, str]
    errors: list[PortmoneErrorDetail]

    @property
    def bill_id(self) -> str | None:
        candidates = [
            self.data.get("bill.billId"),
            self.data.get("bill.bill_id"),
            self.data.get("bill.id"),
            self.data.get("billId"),
            self.data.get("bill_id"),
        ]
        for candidate in candidates:
            if candidate:
                return candidate
        return None

    @property
    def contract_number(self) -> str | None:
        return (
            self.data.get("bill.contractNumber")
            or self.data.get("contractNumber")
            or self.data.get("bill.contract_number")
        )


class PortmoneError(Exception):
    """Base error for PortmoneDirect client."""


class PortmoneTransportError(PortmoneError):
    """Raised when HTTP transport or TLS fails before reaching Portmone."""


class PortmoneResponseError(PortmoneError):
    """Raised when Portmone responds with `<rsp status=\"fail\">`."""

    def __init__(self, response: PortmoneResponse) -> None:
        self.response = response
        first_error = response.errors[0] if response.errors else None
        message = (
            f"Portmone responded with status={response.status} "
            f"code={first_error.code if first_error else 'unknown'}"
        )
        super().__init__(message)


class PortmoneDirectClient:
    """Thin async wrapper around PortmoneDirect form-encoded API."""

    def __init__(
        self,
        settings: AppSettings | None = None,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._auth = {
            "login": self.settings.portmone_login,
            "password": self.settings.portmone_password,
            "version": self.settings.portmone_version,
        }
        self._lang = self.settings.portmone_lang
        base = self.settings.portmone_api_base.rstrip("/") + "/"
        cert = None
        if self.settings.portmone_cert_path:
            cert_path = Path(self.settings.portmone_cert_path)
            if cert_path.exists() and cert_path.is_file():
                cert = str(cert_path)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(base_url=base, cert=cert, timeout=timeout)

    async def call(self, method: str, **params: Any) -> PortmoneResponse:
        payload = {"method": method, **self._auth, **params}
        if self._lang:
            payload["lang"] = self._lang

        try:
            response = await self._client.post("", data=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - delegated to retry logic
            raise PortmoneTransportError(str(exc)) from exc

        parsed = parse_portmone_response(response.text)
        if parsed.status != "ok":
            raise PortmoneResponseError(parsed)
        return parsed

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "PortmoneDirectClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()


def parse_portmone_response(xml_text: str) -> PortmoneResponse:
    root = parse_xml_document(xml_text)
    status = root.attrib.get("status", "fail").lower()
    data: dict[str, str] = {}
    errors: list[PortmoneErrorDetail] = []

    for child in root:
        if child.tag.lower() == "error":
            errors.append(
                PortmoneErrorDetail(
                    code=child.attrib.get("code"),
                    message=(child.text or "").strip() or None,
                )
            )
        elif child.tag.lower() == "error_description":
            description = (child.text or "").strip() or None
            if errors:
                errors[-1].description = description
            else:
                errors.append(PortmoneErrorDetail(code=None, message=None, description=description))
        else:
            data.update(flatten_xml(child))

    return PortmoneResponse(status=status, raw=xml_text, data=data, errors=errors)


def get_operator_payee_id(phone_number: str, settings: AppSettings) -> str:
    """
    Определяет payeeId оператора по номеру телефона.
    
    Args:
        phone_number: Номер телефона в формате 380XXXXXXXXX (12 цифр)
        settings: Настройки приложения с payeeId для каждого оператора
        
    Returns:
        payeeId для соответствующего оператора или общий payeeId по умолчанию
        
    Операторы:
        - Київстар: 039, 067, 068, 096, 097, 098
        - Vodafone: 050, 066, 095, 099
        - lifecell: 063, 073, 093
    """
    if not phone_number.startswith("380") or len(phone_number) != 12:
        # Если номер не в правильном формате, возвращаем общий payeeId
        return settings.portmone_payee_id
    
    prefix = phone_number[3:5]  # Первые 2 цифры после 380
    
    # Київстар: 039, 067, 068, 096, 097, 098
    if prefix in ['39', '67', '68', '96', '97', '98']:
        return settings.portmone_payee_id_kyivstar or settings.portmone_payee_id
    
    # Vodafone: 050, 066, 095, 099
    elif prefix in ['50', '66', '95', '99']:
        return settings.portmone_payee_id_vodafone or settings.portmone_payee_id
    
    # lifecell: 063, 073, 093
    elif prefix in ['63', '73', '93']:
        return settings.portmone_payee_id_lifecell or settings.portmone_payee_id
    
    # Неизвестный оператор - используем общий payeeId
    return settings.portmone_payee_id


__all__ = [
    "PortmoneDirectClient",
    "PortmoneError",
    "PortmoneTransportError",
    "PortmoneResponseError",
    "PortmoneResponse",
    "PortmoneErrorDetail",
    "parse_portmone_response",
    "get_operator_payee_id",
]

