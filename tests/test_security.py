from libs.common import get_settings
from libs.common.security import JwtService


def test_jwt_service_roundtrip(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy-token")
    monkeypatch.setenv("ENCRYPTION_SECRET", "secret")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    settings = get_settings()
    service = JwtService(settings)
    token = service.issue("subject", extra={"role": "admin"})
    decoded = service.verify(token)
    assert decoded["sub"] == "subject"
    assert decoded["role"] == "admin"

