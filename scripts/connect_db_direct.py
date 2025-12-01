#!/usr/bin/env python3
"""Script to connect directly to Heroku PostgreSQL database."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine

from libs.data.models.user import User
from libs.data.models.receipt import Receipt
from libs.data.models.bonus import BonusTransaction


# Database connection string
DATABASE_URL = "postgres://udsoi5dli0ta96:p7733ead1284915f292e44768fde954be2befd8c5c76f3216479425e681bfaf3a@c1erdbv5s7bd6i.cluster-czz5s0kz4scl.eu-west-1.rds.amazonaws.com:5432/ddv1kml2m2u456"

# Convert postgres:// to postgresql+asyncpg:// for async SQLAlchemy
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://")


async def inspect_database():
    """Inspect database contents."""
    print("=" * 80)
    print("Database Content Inspection")
    print("=" * 80)
    
    # Create engine with SSL for Heroku Postgres
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
            # Users
            print("\n" + "=" * 80)
            print("👥 USERS")
            print("=" * 80)
            
            result = await conn.execute(select(User))
            users = result.scalars().all()
            
            print(f"\nTotal users: {len(users)}")
            
            if users:
                print("\n📋 All users:")
                print("-" * 80)
                for user in users:
                    print(f"  ID: {user.id}")
                    print(f"  Telegram ID: {user.telegram_id}")
                    print(f"  Phone: {user.phone_number or 'Not set'}")
                    print(f"  Phone Hash: {user.phone_hash or 'Not set'}")
                    print(f"  Locale: {user.locale}")
                    print(f"  Consent Timestamp: {user.consent_timestamp or 'Not given'}")
                    print(f"  Created: {user.created_at}")
                    print(f"  Updated: {user.updated_at}")
                    print()
            
            # Receipts
            print("\n" + "=" * 80)
            print("🧾 RECEIPTS")
            print("=" * 80)
            
            result = await conn.execute(select(Receipt))
            receipts = result.scalars().all()
            
            print(f"\nTotal receipts: {len(receipts)}")
            
            if receipts:
                # Receipts by status
                result = await conn.execute(text("""
                    SELECT status, COUNT(*) 
                    FROM receipts 
                    GROUP BY status
                    ORDER BY COUNT(*) DESC
                """))
                status_stats = result.fetchall()
                
                print("\n📊 Receipts by status:")
                for status, count in status_stats:
                    print(f"  {status}: {count}")
                
                print("\n📋 Recent receipts (last 10):")
                print("-" * 80)
                for receipt in receipts[:10]:
                    print(f"  ID: {receipt.id}")
                    print(f"  User ID: {receipt.user_id}")
                    print(f"  Status: {receipt.status}")
                    print(f"  Merchant: {receipt.merchant or 'Unknown'}")
                    print(f"  Purchase Date: {receipt.purchase_ts or 'Not set'}")
                    print(f"  Created: {receipt.created_at}")
                    print()
            
            # Bonus Transactions
            print("\n" + "=" * 80)
            print("💰 BONUS TRANSACTIONS")
            print("=" * 80)
            
            result = await conn.execute(select(BonusTransaction))
            bonuses = result.scalars().all()
            
            print(f"\nTotal bonus transactions: {len(bonuses)}")
            
            if bonuses:
                # Bonuses by status
                result = await conn.execute(text("""
                    SELECT payout_status, COUNT(*) 
                    FROM bonus_transactions 
                    GROUP BY payout_status
                    ORDER BY COUNT(*) DESC
                """))
                status_stats = result.fetchall()
                
                print("\n📊 Bonus transactions by status:")
                for status, count in status_stats:
                    print(f"  {status}: {count}")
                
                print("\n📋 Recent bonus transactions (last 10):")
                print("-" * 80)
                for bonus in bonuses[:10]:
                    amount_uah = bonus.amount / 100
                    print(f"  ID: {bonus.id}")
                    print(f"  User ID: {bonus.user_id}")
                    print(f"  Receipt ID: {bonus.receipt_id}")
                    print(f"  MSISDN: {bonus.msisdn}")
                    print(f"  Amount: {bonus.amount} kopecks ({amount_uah:.2f} UAH)")
                    print(f"  Status: {bonus.payout_status}")
                    print(f"  Provider: {bonus.provider}")
                    if bonus.portmone_status:
                        print(f"  Portmone Status: {bonus.portmone_status}")
                    if bonus.portmone_error_code:
                        print(f"  Portmone Error: {bonus.portmone_error_code}")
                    print(f"  Created: {bonus.created_at}")
                    print()
            
            # Line Items
            print("\n" + "=" * 80)
            print("🛒 LINE ITEMS")
            print("=" * 80)
            
            result = await conn.execute(text("SELECT COUNT(*) FROM line_items"))
            total_items = result.scalar()
            print(f"\nTotal line items: {total_items}")
            
            if total_items > 0:
                result = await conn.execute(text("""
                    SELECT 
                        receipt_id,
                        COUNT(*) as item_count,
                        SUM(total_price) as total_sum_kopecks
                    FROM line_items
                    GROUP BY receipt_id
                    ORDER BY receipt_id
                    LIMIT 10
                """))
                items_stats = result.fetchall()
                
                print("\n📋 Line items by receipt (first 10):")
                for receipt_id, count, total in items_stats:
                    total_uah = total / 100 if total else 0
                    print(f"  Receipt {receipt_id}: {count} items, {total} kopecks ({total_uah:.2f} UAH)")
            
            # Database info
            print("\n" + "=" * 80)
            print("📈 DATABASE INFO")
            print("=" * 80)
            
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"\nPostgreSQL version: {version.split(',')[0]}")
            
            result = await conn.execute(text("SELECT current_database()"))
            db_name = result.scalar()
            print(f"Database name: {db_name}")
            
            result = await conn.execute(text("""
                SELECT 
                    pg_size_pretty(pg_database_size(current_database())) as db_size
            """))
            db_size = result.scalar()
            print(f"Database size: {db_size}")
        
        await engine.dispose()
        
        print("\n" + "=" * 80)
        print("✅ Database inspection completed!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(inspect_database())
    sys.exit(0 if success else 1)

