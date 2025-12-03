#!/usr/bin/env python3
"""
Скрипт для удаления всех пользователей и чеков из базы данных Heroku.
Использует Heroku CLI для получения DATABASE_URL.
"""

import asyncio
import subprocess
import sys
import ssl
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

HEROKU_APP_NAME = "darnitsacashbot"


def get_database_url_from_heroku() -> str:
    """Получить DATABASE_URL из Heroku используя Heroku CLI или переменную окружения."""
    # Сначала проверяем переменную окружения
    import os
    db_url = os.getenv("DATABASE_URL")
    
    if db_url:
        print("✅ DATABASE_URL получен из переменной окружения")
        return db_url
    
    # Если нет в окружении, пробуем получить через Heroku CLI
    print("📡 Получение DATABASE_URL из Heroku через CLI...")
    
    try:
        # Пробуем использовать npx heroku
        result = subprocess.run(
            ["npx", "--yes", "heroku", "config:get", "DATABASE_URL", "--app", HEROKU_APP_NAME],
            capture_output=True,
            text=True,
            check=True,
        )
        
        db_url = result.stdout.strip()
        
        if not db_url:
            raise ValueError("DATABASE_URL пустой")
        
        print("✅ DATABASE_URL получен через Heroku CLI")
        return db_url
        
    except subprocess.CalledProcessError as e:
        print("❌ Ошибка при получении DATABASE_URL из Heroku:")
        print(f"   Код возврата: {e.returncode}")
        print(f"   Вывод: {e.stderr}")
        print("\n   Попробуйте установить переменную окружения DATABASE_URL")
        print("   или убедитесь, что:")
        print("   1. Heroku CLI доступен через npx")
        print("   2. Выполнен вход: heroku login")
        sys.exit(1)
    except FileNotFoundError:
        print("⚠️  npx не найден, используем прямой DATABASE_URL")
        # Используем прямой DATABASE_URL из скрипта connect_db_direct.py
        direct_db_url = "postgres://udsoi5dli0ta96:p7733ead1284915f292e44768fde954be2befd8c5c76f3216479425e681bfaf3a@c1erdbv5s7bd6i.cluster-czz5s0kz4scl.eu-west-1.rds.amazonaws.com:5432/ddv1kml2m2u456"
        print("✅ Используется прямой DATABASE_URL")
        return direct_db_url


async def delete_all_data():
    """Удалить все данные из базы данных."""
    print("=" * 60)
    print("🧹 Очистка базы данных Heroku")
    print("=" * 60)
    print(f"Приложение: {HEROKU_APP_NAME}")
    print("=" * 60)
    
    # Получаем DATABASE_URL через Heroku CLI
    db_url = get_database_url_from_heroku()
    
    # Конвертируем postgres:// в postgresql+asyncpg:// для async SQLAlchemy
    async_db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    
    print("\n🔌 Подключение к базе данных...")
    
    # Настраиваем SSL для Heroku Postgres
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    engine = create_async_engine(
        async_db_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"ssl": ssl_context},
    )
    
    transaction_started = False
    
    try:
        async with engine.begin() as conn:
            # Начинаем транзакцию (begin() автоматически начинает транзакцию)
            transaction_started = True
            
            print("✅ Подключено к базе данных\n")
            print("🗑️  Удаление данных...\n")
            
            # 1. Удаляем line_items (зависит от receipts)
            print("1️⃣  Удаление line_items...")
            result = await conn.execute(text("DELETE FROM line_items"))
            line_items_count = result.rowcount
            print(f"   ✅ Удалено {line_items_count} записей из line_items")
            
            # 2. Удаляем bonus_transactions (зависит от receipts и users)
            print("2️⃣  Удаление bonus_transactions...")
            result = await conn.execute(text("DELETE FROM bonus_transactions"))
            bonus_count = result.rowcount
            print(f"   ✅ Удалено {bonus_count} записей из bonus_transactions")
            
            # 3. Удаляем receipts (чеки) (зависит от users)
            print("3️⃣  Удаление receipts (чеки)...")
            result = await conn.execute(text("DELETE FROM receipts"))
            receipts_count = result.rowcount
            print(f"   ✅ Удалено {receipts_count} записей из receipts")
            
            # 4. Удаляем users
            print("4️⃣  Удаление users...")
            result = await conn.execute(text("DELETE FROM users"))
            users_count = result.rowcount
            print(f"   ✅ Удалено {users_count} записей из users")
            
            # Транзакция автоматически коммитится при выходе из блока begin()
            print("\n✅ Все данные успешно удалены!")
            
            # Показываем статистику
            print("\n📊 Статистика удаления:")
            print(f"   - Пользователей: {users_count}")
            print(f"   - Чеков: {receipts_count}")
            print(f"   - Транзакций бонусов: {bonus_count}")
            print(f"   - Позиций чеков: {line_items_count}")
            
    except Exception as e:
        print(f"\n❌ Ошибка при удалении данных:")
        print(f"   Тип ошибки: {type(e).__name__}")
        print(f"   Сообщение: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await engine.dispose()
        print("\n🔌 Соединение с базой данных закрыто")
    
    return True


if __name__ == "__main__":
    print("\n⚠️  ВНИМАНИЕ: Этот скрипт удалит ВСЕ данные из базы данных!")
    print("   Нажмите Ctrl+C для отмены или подождите 3 секунды...\n")
    
    try:
        # Даем пользователю время отменить операцию
        import time
        for i in range(3, 0, -1):
            print(f"   Запуск через {i}...", end="\r")
            time.sleep(1)
        print("   Запуск...                    ")
    except KeyboardInterrupt:
        print("\n\n❌ Операция отменена пользователем")
        sys.exit(0)
    
    success = asyncio.run(delete_all_data())
    sys.exit(0 if success else 1)

