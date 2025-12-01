from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from libs.common import AppSettings, get_settings


class Encryptor:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        key = self._ensure_key_length(self.settings.encryption_secret)
        self.fernet = Fernet(key)

    @staticmethod
    def _ensure_key_length(secret: str) -> bytes:
        try:
            return secret.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Encryption secret must be UTF-8 compatible")

    def encrypt(self, value: str) -> str:
        return self.fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        try:
            return self.fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Invalid encrypted payload") from exc

