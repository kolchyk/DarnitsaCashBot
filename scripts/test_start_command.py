#!/usr/bin/env python3
"""Скрипт для тестирования команды /start через API Gateway."""

import asyncio
import sys
from pathlib import Path

import httpx
from libs.common import get_settings


async def test_start_command():
    """Тестирует команду /start через API Gateway."""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ КОМАНДЫ /start")
    print("=" * 60)
    
    settings = get_settings()
    api_url = settings.api_gateway_url
    print(f"\nAPI Gateway URL: {api_url}\n")
    
    # Тестовый telegram_id
    test_telegram_id = 123456789
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Тест 1: Новый пользователь без номера телефона
        print("-" * 60)
        print("Тест 1: Регистрация нового пользователя БЕЗ номера телефона")
        print("-" * 60)
        
        try:
            payload = {
                "telegram_id": test_telegram_id,
                "phone_number": None,
                "locale": "uk"
            }
            print(f"Отправка запроса: POST {api_url}/bot/users")
            print(f"Payload: {payload}")
            
            response = await client.post(f"{api_url}/bot/users", json=payload)
            
            print(f"\nСтатус ответа: {response.status_code}")
            print(f"Ответ сервера:")
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Успешно!")
                print(f"  User ID: {data.get('id')}")
                print(f"  Telegram ID: {data.get('telegram_id')}")
                print(f"  Locale: {data.get('locale')}")
                print(f"  Has Phone: {data.get('has_phone')}")
                
                if not data.get('has_phone'):
                    print("\n  📱 Ожидаемое поведение бота:")
                    print("     - Бот должен показать приветствие")
                    print("     - Бот должен запросить номер телефона")
                    print("     - Бот должен показать кнопку 'Share phone number'")
                else:
                    print("\n  ⚠️  Неожиданно: has_phone=True для нового пользователя")
            else:
                print(f"  ❌ Ошибка: {response.status_code}")
                print(f"  Ответ: {response.text}")
                
        except httpx.ConnectError as e:
            print(f"\n❌ Не удалось подключиться к API Gateway: {e}")
            print("   Убедитесь, что API Gateway запущен на Heroku или локально")
            return False
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Тест 2: Пользователь с номером телефона
        print("\n" + "-" * 60)
        print("Тест 2: Обновление пользователя С номером телефона")
        print("-" * 60)
        
        try:
            payload = {
                "telegram_id": test_telegram_id,
                "phone_number": "+380501234567",
                "locale": "uk"
            }
            print(f"Отправка запроса: POST {api_url}/bot/users")
            print(f"Payload: {payload}")
            
            response = await client.post(f"{api_url}/bot/users", json=payload)
            
            print(f"\nСтатус ответа: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Успешно!")
                print(f"  User ID: {data.get('id')}")
                print(f"  Telegram ID: {data.get('telegram_id')}")
                print(f"  Locale: {data.get('locale')}")
                print(f"  Has Phone: {data.get('has_phone')}")
                
                if data.get('has_phone'):
                    print("\n  📱 Ожидаемое поведение бота:")
                    print("     - Бот должен показать приветствие")
                    print("     - Бот должен сообщить, что номер уже сохранен")
                    print("     - Бот НЕ должен показывать кнопку запроса контакта")
                else:
                    print("\n  ⚠️  Неожиданно: has_phone=False после добавления номера")
            else:
                print(f"  ❌ Ошибка: {response.status_code}")
                print(f"  Ответ: {response.text}")
                
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Тест 3: Проверка истории (опционально)
        print("\n" + "-" * 60)
        print("Тест 3: Проверка истории пользователя")
        print("-" * 60)
        
        try:
            response = await client.get(f"{api_url}/bot/history/{test_telegram_id}")
            
            print(f"Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                history = response.json()
                print(f"  ✅ Успешно!")
                print(f"  Количество чеков: {len(history)}")
                if history:
                    print(f"  Последний чек: {history[0]}")
                else:
                    print("  История пуста (ожидаемо для нового пользователя)")
            elif response.status_code == 404:
                print(f"  ⚠️  Пользователь не найден (404)")
            else:
                print(f"  ❌ Ошибка: {response.status_code}")
                print(f"  Ответ: {response.text}")
                
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)
    print("\nПримечание:")
    print("Этот скрипт тестирует API endpoint, который вызывается ботом")
    print("при обработке команды /start. Для полного теста отправьте")
    print("команду /start боту в Telegram.")
    
    return True


if __name__ == "__main__":
    try:
        asyncio.run(test_start_command())
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем.")
        sys.exit(0)

