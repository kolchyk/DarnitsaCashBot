#!/usr/bin/env python3
"""Quick script to view users from database."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from libs.common import get_settings
from libs.data.models.user import User


async def show_users():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.connect() as conn:
        result = await conn.execute(select(User))
        users = result.scalars().all()
        print('\n👥 ПОЛЬЗОВАТЕЛИ:')
        print('=' * 80)
        for user in users:
            print(f'ID: {user.id}')
            print(f'Telegram ID: {user.telegram_id}')
            print(f'Phone: {user.phone_number or "Not set"}')
            print(f'Locale: {user.locale}')
            print(f'Consent: {user.consent_timestamp or "Not given"}')
            print(f'Created: {user.created_at}')
            print('-' * 80)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(show_users())

