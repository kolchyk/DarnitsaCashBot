#!/usr/bin/env python3
"""Show users table from database."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

# Database connection string
DATABASE_URL = "postgres://udsoi5dli0ta96:p7733ead1284915f292e44768fde954be2befd8c5c76f3216479425e681bfaf3a@c1erdbv5s7bd6i.cluster-czz5s0kz4scl.eu-west-1.rds.amazonaws.com:5432/ddv1kml2m2u456"

# Convert postgres:// to postgresql+asyncpg:// for async SQLAlchemy
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://")


async def show_users_table():
    """Show users table."""
    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    engine = create_async_engine(
        ASYNC_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        connect_args={"ssl": ssl_context},
    )
    
    try:
        async with engine.connect() as conn:
            # Get all users using raw SQL for better control
            result = await conn.execute(text("""
                SELECT 
                    id,
                    telegram_id,
                    phone_number,
                    phone_hash,
                    locale,
                    consent_timestamp,
                    created_at,
                    updated_at
                FROM users
                ORDER BY created_at DESC
            """))
            
            users = result.fetchall()
            
            print("\n" + "=" * 120)
            print("👥 ТАБЛИЦА USERS")
            print("=" * 120)
            print(f"\nВсего пользователей: {len(users)}\n")
            
            if not users:
                print("Таблица пуста.")
                return
            
            # Print header
            print(f"{'ID':<38} {'Telegram ID':<15} {'Phone':<20} {'Locale':<8} {'Consent':<25} {'Created':<25}")
            print("-" * 120)
            
            # Print rows
            for user in users:
                user_id, telegram_id, phone, phone_hash, locale, consent, created_at, updated_at = user
                
                phone_display = phone[:17] + "..." if phone and len(phone) > 20 else (phone or "—")
                consent_display = consent.strftime("%Y-%m-%d %H:%M:%S") if consent else "—"
                created_display = created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "—"
                
                print(f"{str(user_id):<38} {telegram_id:<15} {phone_display:<20} {locale:<8} {consent_display:<25} {created_display:<25}")
            
            print("\n" + "=" * 120)
            print("\n📋 Детальная информация:")
            print("-" * 120)
            
            for user in users:
                user_id, telegram_id, phone, phone_hash, locale, consent, created_at, updated_at = user
                print(f"\n👤 Пользователь:")
                print(f"   ID: {user_id}")
                print(f"   Telegram ID: {telegram_id}")
                print(f"   Phone: {phone or 'Не указан'}")
                print(f"   Phone Hash: {phone_hash or 'Не указан'}")
                print(f"   Locale: {locale}")
                print(f"   Consent Timestamp: {consent.strftime('%Y-%m-%d %H:%M:%S') if consent else 'Не дан'}")
                print(f"   Created: {created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else '—'}")
                print(f"   Updated: {updated_at.strftime('%Y-%m-%d %H:%M:%S') if updated_at else '—'}")
        
        await engine.dispose()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(show_users_table())
    sys.exit(0 if success else 1)

