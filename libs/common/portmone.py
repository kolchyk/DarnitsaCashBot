from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from prometheus_client import Counter, Histogram, REGISTRY

from libs.common import AppSettings, get_settings
from libs.common.xml_utils import XMLParseError, flatten_xml, parse_xml_document


# Prometheus metrics - created once, reused if module reloads
def _get_or_create_counter(name, documentation, labelnames):
    """Get existing Counter from registry or create a new one."""
    try:
        return Counter(name, documentation, labelnames)
    except ValueError:
        # Metric already exists, find and return it
        # Search through all collectors to find the one with matching name
        for collector in list(REGISTRY._collector_to_names.keys()):
            if hasattr(collector, '_name') and collector._name == name and isinstance(collector, Counter):
                return collector
        # If not found, raise the original error
        raise


def _get_or_create_histogram(name, documentation, labelnames, buckets):
    """Get existing Histogram from registry or create a new one."""
    try:
        return Histogram(name, documentation, labelnames, buckets=buckets)
    except ValueError:
        # Metric already exists, find and return it
        # Search through all collectors to find the one with matching name
        for collector in list(REGISTRY._collector_to_names.keys()):
            if hasattr(collector, '_name') and collector._name == name and isinstance(collector, Histogram):
                return collector
        # If not found, raise the original error
        raise


PORTMONE_REQUEST_TOTAL = _get_or_create_counter(
    "portmone_request_total",
    "Total PortmoneDirect requests",
    ["method", "status"],
)
PORTMONE_FAIL_TOTAL = _get_or_create_counter(
    "portmone_fail_total",
    "Failed PortmoneDirect requests grouped by error code",
    ["method", "code"],
)
PORTMONE_REQUEST_LATENCY = _get_or_create_histogram(
    "portmone_request_latency_seconds",
    "Latency for PortmoneDirect requests",
    ["method"],
    buckets=(0.1, 0.3, 1, 2, 5, 10),
)


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

        start = time.perf_counter()
        try:
            response = await self._client.post("", data=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - delegated to retry logic
            PORTMONE_FAIL_TOTAL.labels(method=method, code="transport").inc()
            raise PortmoneTransportError(str(exc)) from exc
        duration = time.perf_counter() - start

        parsed = parse_portmone_response(response.text)
        PORTMONE_REQUEST_TOTAL.labels(method=method, status=parsed.status).inc()
        PORTMONE_REQUEST_LATENCY.labels(method=method).observe(duration)
        if parsed.status != "ok":
            code = parsed.errors[0].code if parsed.errors else "unknown"
            PORTMONE_FAIL_TOTAL.labels(method=method, code=code or "unknown").inc()
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


__all__ = [
    "PortmoneDirectClient",
    "PortmoneError",
    "PortmoneTransportError",
    "PortmoneResponseError",
    "PortmoneResponse",
    "PortmoneErrorDetail",
    "parse_portmone_response",
]

