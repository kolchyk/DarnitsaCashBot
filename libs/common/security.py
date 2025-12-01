from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from libs.common import AppSettings, get_settings


class JwtService:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()

    def issue(self, subject: str, *, expires_in_minutes: int = 30, extra: dict[str, Any] | None = None) -> str:
        payload: dict[str, Any] = {
            "sub": subject,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        }
        if extra:
            payload.update(extra)
        return jwt.encode(payload, self.settings.jwt_secret, algorithm=self.settings.jwt_alg)

    def verify(self, token: str) -> dict[str, Any]:
        return jwt.decode(token, self.settings.jwt_secret, algorithms=[self.settings.jwt_alg])

