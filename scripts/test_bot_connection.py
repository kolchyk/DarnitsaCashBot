#!/usr/bin/env python3
"""Скрипт для проверки подключения Telegram бота и API Gateway."""

import asyncio
import sys
from pathlib import Path

import httpx
from aiogram import Bot
from libs.common import get_settings


async def check_bot_token():
    """Проверяет валидность токена бота."""
    print("=" * 60)
    print("1. Проверка токена Telegram бота...")
    print("=" * 60)
    
    settings = get_settings()
    if not settings.telegram_bot_token:
        print("❌ TELEGRAM_BOT_TOKEN не установлен!")
        return False
    
    print(f"✅ Токен найден: {settings.telegram_bot_token[:10]}...")
    
    try:
        bot = Bot(token=settings.telegram_bot_token)
        me = await bot.get_me()
        print(f"✅ Бот подключен: @{me.username} ({me.first_name})")
        await bot.session.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к Telegram API: {e}")
        return False


async def check_api_gateway():
    """Проверяет доступность API Gateway."""
    print("\n" + "=" * 60)
    print("2. Проверка доступности API Gateway...")
    print("=" * 60)
    
    settings = get_settings()
    api_url = settings.api_gateway_url
    print(f"URL API Gateway: {api_url}")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Проверяем health endpoint
            try:
                response = await client.get(f"{api_url}/healthz")
                if response.status_code == 200:
                    print(f"✅ API Gateway доступен (healthz: {response.status_code})")
                else:
                    print(f"⚠️  API Gateway отвечает, но статус: {response.status_code}")
            except httpx.ConnectError:
                print(f"❌ Не удалось подключиться к API Gateway по адресу {api_url}")
                print("   Убедитесь, что API Gateway запущен:")
                print("   poetry run uvicorn apps.api_gateway.main:app --reload")
                return False
            
            # Проверяем endpoint регистрации пользователя
            try:
                test_payload = {
                    "telegram_id": 123456789,
                    "phone_number": None,
                    "locale": "uk"
                }
                response = await client.post(f"{api_url}/bot/users", json=test_payload)
                if response.status_code in (200, 201):
                    print(f"✅ Endpoint /bot/users доступен (статус: {response.status_code})")
                    return True
                else:
                    print(f"⚠️  Endpoint /bot/users вернул статус: {response.status_code}")
                    print(f"   Ответ: {response.text[:200]}")
                    return False
            except Exception as e:
                print(f"❌ Ошибка при проверке /bot/users: {e}")
                return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False


def check_env_variables():
    """Проверяет наличие необходимых переменных окружения."""
    print("\n" + "=" * 60)
    print("3. Проверка переменных окружения...")
    print("=" * 60)
    
    settings = get_settings()
    
    required_vars = {
        "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token,
        "API_GATEWAY_URL": settings.api_gateway_url,
        "ENCRYPTION_SECRET": settings.encryption_secret,
    }
    
    all_ok = True
    for var_name, value in required_vars.items():
        if value:
            print(f"✅ {var_name}: установлен")
        else:
            print(f"❌ {var_name}: НЕ установлен")
            all_ok = False
    
    optional_vars = {
        "TELEGRAM_ADMIN_IDS": settings.telegram_admin_ids,
        "TELEGRAM_WEBHOOK_URL": settings.telegram_webhook_url,
    }
    
    print("\nОпциональные переменные:")
    for var_name, value in optional_vars.items():
        if value:
            print(f"✅ {var_name}: {value}")
        else:
            print(f"⚪ {var_name}: не установлен (опционально)")
    
    return all_ok


async def main():
    """Главная функция."""
    print("\n🔍 Диагностика подключения Telegram бота\n")
    
    # Проверка переменных окружения
    env_ok = check_env_variables()
    if not env_ok:
        print("\n❌ Не все обязательные переменные окружения установлены!")
        print("   Проверьте файл .env или переменные окружения системы.")
        sys.exit(1)
    
    # Проверка токена бота
    bot_ok = await check_bot_token()
    if not bot_ok:
        print("\n❌ Проблема с токеном бота!")
        print("   Проверьте правильность TELEGRAM_BOT_TOKEN.")
        sys.exit(1)
    
    # Проверка API Gateway
    api_ok = await check_api_gateway()
    if not api_ok:
        print("\n❌ Проблема с API Gateway!")
        print("   Запустите API Gateway:")
        print("   poetry run uvicorn apps.api_gateway.main:app --reload")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ Все проверки пройдены успешно!")
    print("=" * 60)
    print("\nБот должен работать корректно.")
    print("Запустите бота командой:")
    print("  poetry run python -m apps.telegram_bot.main")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем.")
        sys.exit(0)

