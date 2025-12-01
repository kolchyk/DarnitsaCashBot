from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from libs.common import AppSettings, get_settings


class Encryptor:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        key = hashlib.sha256(self.settings.encryption_secret.encode("utf-8")).digest()
        self.fernet = Fernet(base64.urlsafe_b64encode(key))

    def encrypt(self, value: str) -> str:
        return self.fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        try:
            return self.fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Invalid encrypted payload") from exc

    @staticmethod
    def hash_value(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

