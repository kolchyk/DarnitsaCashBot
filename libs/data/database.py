from __future__ import annotations

import os
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
        # Add SSL parameters for Heroku Postgres
        connect_args = {}
        if os.getenv("DATABASE_URL"):
            import ssl
            
            # Determine SSL mode based on environment and configuration
            ssl_mode = settings.postgres_ssl_mode.lower()
            
            if ssl_mode == "disable":
                # No SSL
                connect_args = {}
            elif ssl_mode == "require":
                # SSL required but no certificate verification (for Heroku compatibility)
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                connect_args = {"ssl": ssl_context}
            elif ssl_mode == "verify-full":
                # Full SSL with certificate verification (recommended for production)
                if settings.app_env == "prod":
                    ssl_context = ssl.create_default_context()
                    connect_args = {"ssl": ssl_context}
                else:
                    # In non-prod, use require mode for compatibility
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    connect_args = {"ssl": ssl_context}
            else:
                # Default: prefer SSL with relaxed verification (for Heroku compatibility)
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                connect_args = {"ssl": ssl_context}
        
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.app_env == "local",
            connect_args=connect_args,
            pool_pre_ping=True,  # Verify connections before using them
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

