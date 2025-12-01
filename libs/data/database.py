from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from libs.common import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "local",
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session

