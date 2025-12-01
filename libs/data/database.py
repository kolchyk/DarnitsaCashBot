from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from libs.common import get_settings

_engine = None
_async_session_factory = None


def _init_engine():
    """Initialize database engine lazily."""
    global _engine, _async_session_factory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.app_env == "local",
        )
        _async_session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine, _async_session_factory


def __getattr__(name: str):
    """Lazy initialization of engine and async_session_factory."""
    if name == "engine":
        engine, _ = _init_engine()
        return engine
    if name == "async_session_factory":
        _, factory = _init_engine()
        return factory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def get_async_session() -> AsyncIterator[AsyncSession]:
    _, factory = _init_engine()
    async with factory() as session:
        yield session

