#!/usr/bin/env python3
"""Script to inspect database contents in detail."""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from libs.common import get_settings
from libs.data.models.bonus import BonusTransaction, BonusStatus
from libs.data.models.receipt import Receipt, ReceiptStatus
from libs.data.models.user import User


async def inspect_database():
    """Inspect database contents in detail."""
    print("=" * 80)
    print("Database Content Inspection")
    print("=" * 80)
    
    try:
        settings = get_settings()
        
        # Create engine
        print("\n🔌 Connecting to database...")
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
        )
        
        async with engine.connect() as conn:
            # Users section
            print("\n" + "=" * 80)
            print("👥 USERS")
            print("=" * 80)
            
            result = await conn.execute(select(func.count()).select_from(User))
            total_users = result.scalar()
            print(f"\nTotal users: {total_users}")
            
            if total_users > 0:
                # Recent users
                result = await conn.execute(
                    select(User)
                    .order_by(User.created_at.desc())
                    .limit(10)
                )
                users = result.scalars().all()
                
                print("\n📋 Recent users (last 10):")
                print("-" * 80)
                for user in users:
                    print(f"  ID: {user.id}")
                    print(f"  Telegram ID: {user.telegram_id}")
                    print(f"  Phone: {user.phone_number or 'Not set'}")
                    print(f"  Locale: {user.locale}")
                    print(f"  Consent: {user.consent_timestamp or 'Not given'}")
                    print(f"  Created: {user.created_at}")
                    print()
                
                # Users by locale
                result = await conn.execute(
                    select(User.locale, func.count(User.id))
                    .group_by(User.locale)
                )
                locale_stats = result.all()
                print("\n📊 Users by locale:")
                for locale, count in locale_stats:
                    print(f"  {locale}: {count}")
            
            # Receipts section
            print("\n" + "=" * 80)
            print("🧾 RECEIPTS")
            print("=" * 80)
            
            result = await conn.execute(select(func.count()).select_from(Receipt))
            total_receipts = result.scalar()
            print(f"\nTotal receipts: {total_receipts}")
            
            if total_receipts > 0:
                # Receipts by status
                result = await conn.execute(
                    select(Receipt.status, func.count(Receipt.id))
                    .group_by(Receipt.status)
                )
                status_stats = result.all()
                print("\n📊 Receipts by status:")
                for status, count in status_stats:
                    print(f"  {status}: {count}")
                
                # Recent receipts
                result = await conn.execute(
                    select(Receipt)
                    .order_by(Receipt.created_at.desc())
                    .limit(10)
                )
                receipts = result.scalars().all()
                
                print("\n📋 Recent receipts (last 10):")
                print("-" * 80)
                for receipt in receipts:
                    # Get user telegram_id
                    user_result = await conn.execute(
                        select(User.telegram_id).where(User.id == receipt.user_id)
                    )
                    telegram_id = user_result.scalar()
                    
                    # Get line items count
                    items_result = await conn.execute(
                        text("SELECT COUNT(*) FROM line_items WHERE receipt_id = :receipt_id"),
                        {"receipt_id": receipt.id}
                    )
                    items_count = items_result.scalar()
                    
                    print(f"  ID: {receipt.id}")
                    print(f"  User Telegram ID: {telegram_id}")
                    print(f"  Status: {receipt.status}")
                    print(f"  Merchant: {receipt.merchant or 'Unknown'}")
                    print(f"  Purchase date: {receipt.purchase_ts or 'Not set'}")
                    print(f"  Items count: {items_count}")
                    print(f"  Created: {receipt.created_at}")
                    print()
            
            # Bonus Transactions section
            print("\n" + "=" * 80)
            print("💰 BONUS TRANSACTIONS")
            print("=" * 80)
            
            result = await conn.execute(select(func.count()).select_from(BonusTransaction))
            total_bonuses = result.scalar()
            print(f"\nTotal bonus transactions: {total_bonuses}")
            
            if total_bonuses > 0:
                # Bonuses by status
                result = await conn.execute(
                    select(BonusTransaction.payout_status, func.count(BonusTransaction.id))
                    .group_by(BonusTransaction.payout_status)
                )
                status_stats = result.all()
                print("\n📊 Bonus transactions by status:")
                for status, count in status_stats:
                    print(f"  {status}: {count}")
                
                # Total amount by status
                result = await conn.execute(
                    select(
                        BonusTransaction.payout_status,
                        func.sum(BonusTransaction.amount).label("total_amount")
                    )
                    .group_by(BonusTransaction.payout_status)
                )
                amount_stats = result.all()
                print("\n💰 Total amount by status (in kopecks):")
                for status, total_amount in amount_stats:
                    if total_amount:
                        uah = total_amount / 100
                        print(f"  {status}: {total_amount} kopecks ({uah:.2f} UAH)")
                
                # Recent bonus transactions
                result = await conn.execute(
                    select(BonusTransaction)
                    .order_by(BonusTransaction.created_at.desc())
                    .limit(10)
                )
                bonuses = result.scalars().all()
                
                print("\n📋 Recent bonus transactions (last 10):")
                print("-" * 80)
                for bonus in bonuses:
                    # Get user telegram_id
                    user_result = await conn.execute(
                        select(User.telegram_id).where(User.id == bonus.user_id)
                    )
                    telegram_id = user_result.scalar()
                    
                    amount_uah = bonus.amount / 100
                    print(f"  ID: {bonus.id}")
                    print(f"  User Telegram ID: {telegram_id}")
                    print(f"  Receipt ID: {bonus.receipt_id}")
                    print(f"  MSISDN: {bonus.msisdn}")
                    print(f"  Amount: {bonus.amount} kopecks ({amount_uah:.2f} UAH)")
                    print(f"  Status: {bonus.payout_status}")
                    print(f"  Provider: {bonus.provider}")
                    if bonus.portmone_status:
                        print(f"  Portmone status: {bonus.portmone_status}")
                    if bonus.portmone_error_code:
                        print(f"  Portmone error: {bonus.portmone_error_code} - {bonus.portmone_error_description}")
                    print(f"  Retries: {bonus.retries}")
                    print(f"  Created: {bonus.created_at}")
                    print()
            
            # Line Items section
            print("\n" + "=" * 80)
            print("🛒 LINE ITEMS")
            print("=" * 80)
            
            result = await conn.execute(text("SELECT COUNT(*) FROM line_items"))
            total_items = result.scalar()
            print(f"\nTotal line items: {total_items}")
            
            if total_items > 0:
                # Items per receipt stats
                result = await conn.execute(text("""
                    SELECT 
                        COUNT(*) as receipt_count,
                        AVG(item_count) as avg_items,
                        MIN(item_count) as min_items,
                        MAX(item_count) as max_items
                    FROM (
                        SELECT receipt_id, COUNT(*) as item_count
                        FROM line_items
                        GROUP BY receipt_id
                    ) as receipt_items
                """))
                stats = result.fetchone()
                if stats:
                    print(f"\n📊 Line items statistics:")
                    print(f"  Receipts with items: {stats[0]}")
                    print(f"  Average items per receipt: {stats[1]:.2f}")
                    print(f"  Min items per receipt: {stats[2]}")
                    print(f"  Max items per receipt: {stats[3]}")
            
            # Database statistics
            print("\n" + "=" * 80)
            print("📈 DATABASE STATISTICS")
            print("=" * 80)
            
            result = await conn.execute(text("""
                SELECT 
                    pg_size_pretty(pg_database_size(current_database())) as db_size,
                    (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) as connections
            """))
            stats = result.fetchone()
            if stats:
                print(f"\n  Database size: {stats[0]}")
                print(f"  Active connections: {stats[1]}")
            
            # Table sizes
            result = await conn.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """))
            table_sizes = result.fetchall()
            if table_sizes:
                print(f"\n  Table sizes:")
                for schema, table, size in table_sizes:
                    print(f"    {table}: {size}")
        
        await engine.dispose()
        
        print("\n" + "=" * 80)
        print("✅ Database inspection completed successfully!")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error inspecting database:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 Troubleshooting:")
        print("  1. Check DATABASE_URL is set: heroku config:get DATABASE_URL")
        print("  2. Verify PostgreSQL addon is provisioned: heroku addons")
        print("  3. Run migrations: heroku run alembic upgrade head")
        return False


if __name__ == "__main__":
    success = asyncio.run(inspect_database())
    sys.exit(0 if success else 1)

