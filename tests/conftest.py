import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("ENCRYPTION_SECRET", "test-encryption-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from libs.data.models.base import Base


@pytest.fixture(scope="function")
async def session() -> AsyncSession:
    """Создает тестовую сессию базы данных."""
    # Используем in-memory SQLite для тестов
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    
    # Создаем все таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_factory() as session:
        yield session
    
    # Очищаем после теста
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

