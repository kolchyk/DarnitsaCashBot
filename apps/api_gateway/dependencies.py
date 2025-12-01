from __future__ import annotations

from typing import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common import AppSettings, get_settings
from libs.common.analytics import AnalyticsClient
from libs.common.storage import StorageClient
from libs.common.rate_limit import RateLimiter
from libs.data.database import get_async_session


async def get_settings_dep() -> AppSettings:
    return get_settings()


async def get_session_dep() -> AsyncIterator[AsyncSession]:
    """Dependency that provides database session."""
    async for session in get_async_session():
        yield session


def get_storage_client(settings: AppSettings = Depends(get_settings_dep)) -> StorageClient:
    return StorageClient(settings)




def get_analytics(settings: AppSettings = Depends(get_settings_dep)) -> AnalyticsClient:
    return AnalyticsClient(settings)


def get_receipt_rate_limiter(settings: AppSettings = Depends(get_settings_dep)) -> RateLimiter:
    return RateLimiter(prefix="receipt", limit=5, ttl_seconds=60, settings=settings)

