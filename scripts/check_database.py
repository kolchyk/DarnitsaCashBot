#!/usr/bin/env python3
"""Script to check database connection and status."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from libs.common import get_settings
from libs.data.models import Base


async def check_database():
    """Check database connection and status."""
    print("=" * 60)
    print("Database Connection Check")
    print("=" * 60)
    
    try:
        settings = get_settings()
        
        # Show database configuration (without password)
        print("\n📋 Database Configuration:")
        print(f"  Host: {settings.postgres_host}")
        print(f"  Port: {settings.postgres_port}")
        print(f"  Database: {settings.postgres_db}")
        print(f"  User: {settings.postgres_user}")
        print(f"  Using Heroku DATABASE_URL: {settings._heroku_database_url is not None}")
        
        # Create engine
        print("\n🔌 Connecting to database...")
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
        )
        
        # Test connection
        async with engine.connect() as conn:
            # Test basic connection
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ Connection successful!")
            print(f"  PostgreSQL version: {version.split(',')[0]}")
            
            # Check database name
            result = await conn.execute(text("SELECT current_database()"))
            db_name = result.scalar()
            print(f"  Current database: {db_name}")
            
            # List all tables
            print("\n📊 Database Tables:")
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            
            if not tables:
                print("  ⚠️  No tables found in database!")
                print("  💡 Run migrations: heroku run alembic upgrade head")
            else:
                print(f"  Found {len(tables)} table(s):")
                for table in tables:
                    # Get row count
                    try:
                        count_result = await conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                        count = count_result.scalar()
                        print(f"    - {table}: {count} row(s)")
                    except Exception as e:
                        print(f"    - {table}: (error reading count: {e})")
            
            # Check expected tables
            print("\n🔍 Expected Tables Check:")
            expected_tables = {
                "users": "User model",
                "receipts": "Receipt model",
                "line_items": "LineItem model",
                "bonus_transactions": "BonusTransaction model",
                "catalog_items": "CatalogItem model",
                "alembic_version": "Alembic migrations",
            }
            
            missing_tables = []
            for table, description in expected_tables.items():
                if table in tables:
                    print(f"  ✅ {table} ({description})")
                else:
                    print(f"  ❌ {table} ({description}) - MISSING")
                    missing_tables.append(table)
            
            if missing_tables:
                print(f"\n⚠️  Missing {len(missing_tables)} expected table(s)")
                print("  💡 Run migrations: heroku run alembic upgrade head")
            
            # Check Alembic version
            print("\n🔄 Alembic Migration Status:")
            if "alembic_version" in tables:
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                version_num = result.scalar()
                print(f"  Current migration version: {version_num}")
            else:
                print("  ⚠️  No Alembic version table found")
                print("  💡 Database may not be initialized. Run migrations.")
            
            # Check for any errors in recent logs (if possible)
            print("\n📈 Database Statistics:")
            try:
                result = await conn.execute(text("""
                    SELECT 
                        pg_size_pretty(pg_database_size(current_database())) as db_size,
                        (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) as connections
                """))
                stats = result.fetchone()
                print(f"  Database size: {stats[0]}")
                print(f"  Active connections: {stats[1]}")
            except Exception as e:
                print(f"  Could not retrieve statistics: {e}")
        
        await engine.dispose()
        
        print("\n" + "=" * 60)
        print("✅ Database check completed successfully!")
        print("=" * 60)
        
        return len(missing_tables) == 0
        
    except Exception as e:
        print(f"\n❌ Error checking database:")
        print(f"  {type(e).__name__}: {e}")
        print("\n💡 Troubleshooting:")
        print("  1. Check DATABASE_URL is set: heroku config:get DATABASE_URL")
        print("  2. Verify PostgreSQL addon is provisioned: heroku addons")
        print("  3. Run migrations: heroku run alembic upgrade head")
        return False


if __name__ == "__main__":
    success = asyncio.run(check_database())
    sys.exit(0 if success else 1)

