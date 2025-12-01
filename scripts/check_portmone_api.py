#!/usr/bin/env python3
"""
Скрипт для проверки работы API Portmone Direct.

Использование:
    python scripts/check_portmone_api.py

Требуемые переменные окружения:
    - PORTMONE_LOGIN - логин компании-реселера
    - PORTMONE_PASSWORD - пароль компании-реселера
    - PORTMONE_API_BASE - базовый URL API (по умолчанию: https://direct.portmone.com.ua/api/directcash/)
    - PORTMONE_VERSION - версия протокола (по умолчанию: 2)
    - PORTMONE_CERT_PATH - путь к TLS сертификату (опционально)
    - PORTMONE_LANG - язык локализации (uk/ru/en, опционально)
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from libs.common.config import get_settings
from libs.common.portmone import PortmoneDirectClient, PortmoneError, PortmoneResponseError, PortmoneTransportError


async def check_portmone_connection():
    """Проверяет подключение к API Portmone."""
    settings = get_settings()
    
    print("=" * 60)
    print("Проверка подключения к API Portmone Direct")
    print("=" * 60)
    print()
    
    # Выводим конфигурацию (без пароля)
    print("Конфигурация:")
    print(f"  API Base URL: {settings.portmone_api_base}")
    print(f"  Login: {settings.portmone_login}")
    print(f"  Password: {'*' * len(settings.portmone_password) if settings.portmone_password else 'НЕ УСТАНОВЛЕН'}")
    print(f"  Version: {settings.portmone_version}")
    print(f"  Language: {settings.portmone_lang or 'не указан (по умолчанию: uk)'}")
    cert_display = "не указан"
    if settings.portmone_cert_path:
        cert_path = Path(settings.portmone_cert_path)
        if cert_path.exists() and cert_path.is_file():
            cert_display = str(cert_path)
        else:
            cert_display = f"{settings.portmone_cert_path} (файл не найден)"
    print(f"  Certificate: {cert_display}")
    print()
    
    # Проверяем обязательные параметры
    if not settings.portmone_login or settings.portmone_login == "demo_login":
        print("⚠️  ВНИМАНИЕ: PORTMONE_LOGIN не установлен или использует значение по умолчанию!")
        print("   Установите реальный логин через переменную окружения PORTMONE_LOGIN")
        print()
    
    if not settings.portmone_password or settings.portmone_password == "demo_password":
        print("⚠️  ВНИМАНИЕ: PORTMONE_PASSWORD не установлен или использует значение по умолчанию!")
        print("   Установите реальный пароль через переменную окружения PORTMONE_PASSWORD")
        print()
    
    # Пробуем выполнить простой запрос
    print("Попытка подключения к API...")
    print()
    
    client = PortmoneDirectClient(settings)
    
    try:
        # Используем метод для получения информации о доступных компаниях-біллерах
        # Это простой метод, который не требует дополнительных параметров
        print("Выполняем запрос: payers.getPayersList")
        response = await client.call("payers.getPayersList")
        
        print("✅ Подключение успешно!")
        print(f"   Статус ответа: {response.status}")
        print(f"   Данные получены: {'да' if response.data else 'нет'}")
        
        if response.errors:
            print(f"   Предупреждения: {len(response.errors)}")
            for error in response.errors:
                print(f"     - Код: {error.code}, Сообщение: {error.message}")
        
        return True
        
    except PortmoneTransportError as e:
        print("❌ Ошибка транспорта (HTTP/TLS):")
        print(f"   {str(e)}")
        print()
        print("Возможные причины:")
        print("  - Неверный URL API")
        print("  - Проблемы с TLS сертификатом")
        print("  - Проблемы с сетью")
        return False
        
    except PortmoneResponseError as e:
        print("❌ API вернул ошибку:")
        print(f"   Статус: {e.response.status}")
        if e.response.errors:
            for error in e.response.errors:
                print(f"   Код ошибки: {error.code}")
                print(f"   Сообщение: {error.message}")
                if error.description:
                    print(f"   Описание: {error.description}")
        print()
        print("Возможные причины:")
        print("  - Неверный логин или пароль")
        print("  - Недостаточно прав доступа")
        print("  - Неверная версия протокола")
        return False
        
    except PortmoneError as e:
        print(f"❌ Неожиданная ошибка Portmone: {str(e)}")
        return False
        
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {type(e).__name__}: {str(e)}")
        return False
        
    finally:
        await client.aclose()


async def test_bills_create():
    """Тестирует создание счета (требует реальных данных)."""
    settings = get_settings()
    
    print()
    print("=" * 60)
    print("Тест создания счета (bills.create)")
    print("=" * 60)
    print()
    
    # Проверяем наличие необходимых параметров
    if not settings.portmone_payee_id or settings.portmone_payee_id == "100000":
        print("⚠️  PORTMONE_PAYEE_ID не установлен или использует значение по умолчанию")
        print("   Этот тест требует реального payeeId")
        return
    
    client = PortmoneDirectClient(settings)
    
    try:
        # Пример создания тестового счета
        # ВНИМАНИЕ: Это создаст реальный счет, если используются реальные учетные данные!
        print("⚠️  ВНИМАНИЕ: Этот тест создаст реальный счет в системе Portmone!")
        print("   Для тестирования используйте mock-сервер или тестовую среду")
        print()
        
        # Раскомментируйте для реального теста:
        # test_payload = {
        #     "payeeId": settings.portmone_payee_id,
        #     "contractNumber": "TEST123",
        #     "amount": "1.00",
        #     "currency": settings.portmone_default_currency,
        #     "comment": "Test bill creation",
        # }
        # response = await client.call("bills.create", **test_payload)
        # print(f"✅ Счет создан успешно!")
        # print(f"   Bill ID: {response.bill_id}")
        # print(f"   Contract Number: {response.contract_number}")
        
        print("Тест пропущен (закомментирован для безопасности)")
        
    except Exception as e:
        print(f"❌ Ошибка при создании счета: {str(e)}")
    finally:
        await client.aclose()


def main():
    """Главная функция."""
    print()
    
    success = asyncio.run(check_portmone_connection())
    
    if success:
        # Опционально: тест создания счета
        # asyncio.run(test_bills_create())
        pass
    
    print()
    print("=" * 60)
    if success:
        print("✅ Проверка завершена успешно")
        sys.exit(0)
    else:
        print("❌ Проверка завершена с ошибками")
        print()
        print("Убедитесь, что:")
        print("  1. Установлены переменные окружения PORTMONE_LOGIN и PORTMONE_PASSWORD")
        print("  2. PORTMONE_API_BASE указывает на правильный URL")
        print("  3. Если требуется TLS сертификат, установлен PORTMONE_CERT_PATH")
        print("  4. Учетные данные предоставлены менеджером Portmone")
        sys.exit(1)


if __name__ == "__main__":
    main()

