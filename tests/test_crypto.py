from libs.common.crypto import Encryptor
from libs.common.config import get_settings


def test_encryptor_roundtrip(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_SECRET", "super-secret-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    encryptor = Encryptor()
    encrypted = encryptor.encrypt("12345")
    assert encryptor.decrypt(encrypted) == "12345"
    assert Encryptor.hash_value("12345") == Encryptor.hash_value("12345")

