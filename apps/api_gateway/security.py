from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from libs.common import AppSettings, get_settings


async def service_key_guard(
    x_service_key: str | None = Header(default=None),
    settings: AppSettings = Depends(get_settings),
) -> None:
    if not x_service_key or x_service_key != settings.jwt_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

