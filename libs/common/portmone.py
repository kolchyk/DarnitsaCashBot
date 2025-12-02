from __future__ import annotations

import ssl
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
        
        # Validate credentials
        login = self.settings.portmone_login
        password = self.settings.portmone_password
        
        if not login or login == "demo_login":
            raise ValueError(
                "PORTMONE_LOGIN не установлен или использует значение по умолчанию. "
                "Установите правильный логин через переменную окружения PORTMONE_LOGIN."
            )
        
        if not password or password == "demo_password":
            raise ValueError(
                "PORTMONE_PASSWORD не установлен или использует значение по умолчанию. "
                "Установите правильный пароль через переменную окружения PORTMONE_PASSWORD."
            )
        
        self._auth = {
            "login": login,
            "password": password,
            "version": self.settings.portmone_version,
        }
        self._lang = self.settings.portmone_lang
        base = self.settings.portmone_api_base.rstrip("/") + "/"
        cert = None
        if self.settings.portmone_cert_path:
            cert_path = Path(self.settings.portmone_cert_path)
            if cert_path.exists() and cert_path.is_file():
                # Check if we have a separate key file
                if self.settings.portmone_key_path:
                    key_path = Path(self.settings.portmone_key_path)
                    if key_path.exists() and key_path.is_file():
                        # Use tuple format for separate cert and key files
                        cert = (str(cert_path), str(key_path))
                    else:
                        raise ValueError(
                            f"Portmone key file not found: {self.settings.portmone_key_path}"
                        )
                else:
                    # Single file should contain both certificate and private key in PEM format
                    # For client certificate authentication, the file should contain:
                    # -----BEGIN CERTIFICATE-----
                    # ...certificate data...
                    # -----END CERTIFICATE-----
                    # -----BEGIN PRIVATE KEY-----
                    # ...private key data...
                    # -----END PRIVATE KEY-----
                    cert = str(cert_path)
        self._owns_client = client is None
        
        # Configure SSL context for TLS 1.2 (Portmone only supports TLS 1.2)
        # According to Portmone docs: "на даний момент сервером підтримується тільки протокол TLS 1.2"
        # Only apply SSL context for HTTPS URLs (not for HTTP mock servers)
        ssl_context = None
        if base.startswith("https://"):
            ssl_context = ssl.create_default_context()
            # Enforce TLS 1.2 (Portmone requirement)
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
            # Verify server certificate
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        # For Portmone API with client certificate, verify server cert and send client cert
        self._client = client or httpx.AsyncClient(
            base_url=base, 
            cert=cert, 
            timeout=timeout,
            verify=ssl_context if ssl_context else True  # Use custom SSL context with TLS 1.2 enforcement for HTTPS
        )

    async def call(self, method: str, **params: Any) -> PortmoneResponse:
        """
        Вызывает метод Portmone API.
        
        Параметры авторизации (login, password, version) автоматически добавляются к запросу.
        Параметры передаются в формате application/x-www-form-urlencoded согласно документации Portmone.
        
        Args:
            method: Название метода API (например, "bills.create")
            **params: Дополнительные параметры для метода
            
        Returns:
            PortmoneResponse: Ответ от API
            
        Raises:
            PortmoneTransportError: При ошибках сети или TLS
            PortmoneResponseError: При ошибках API (включая ошибки авторизации)
        """
        # Формируем payload: сначала метод, затем авторизация, затем параметры метода
        # Порядок важен согласно документации Portmone
        payload = {"method": method, **self._auth, **params}
        if self._lang:
            payload["lang"] = self._lang

        try:
            # httpx автоматически преобразует словарь в application/x-www-form-urlencoded
            # и устанавливает правильный Content-Type заголовок
            response = await self._client.post("", data=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - delegated to retry logic
            raise PortmoneTransportError(str(exc)) from exc

        parsed = parse_portmone_response(response.text)
        if parsed.status != "ok":
            # Проверяем, не является ли это ошибкой авторизации
            if parsed.errors:
                for error in parsed.errors:
                    error_code = error.code or ""
                    error_msg = error.message or ""
                    # Типичные коды ошибок авторизации в Portmone
                    if any(keyword in error_code.lower() or keyword in error_msg.lower() 
                           for keyword in ["auth", "login", "password", "unauthorized", "авторизац"]):
                        error_msg_full = (
                            f"Ошибка авторизации Portmone: {error_code} - {error_msg}. "
                            f"Проверьте PORTMONE_LOGIN и PORTMONE_PASSWORD."
                        )
                        # Создаем исключение с улучшенным сообщением
                        auth_error = PortmoneResponseError(parsed)
                        auth_error.args = (error_msg_full,) + auth_error.args
                        raise auth_error
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

