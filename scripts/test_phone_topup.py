#!/usr/bin/env python3
"""
Скрипт для тестирования пополнения телефона через Portmone Direct API.

Использование:
    python scripts/test_phone_topup.py
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from libs.common.config import get_settings
from libs.common.portmone import PortmoneDirectClient, PortmoneError, PortmoneResponseError, PortmoneTransportError


def normalize_phone(phone: str) -> str:
    """Нормализует номер телефона в формат 380XXXXXXXXX."""
    # Убираем все нецифровые символы
    digits = ''.join(filter(str.isdigit, phone))
    
    # Если номер начинается с 380, оставляем как есть
    if digits.startswith('380') and len(digits) == 12:
        return digits
    
    # Если номер начинается с 0, заменяем на 380
    if digits.startswith('0') and len(digits) == 10:
        return '380' + digits[1:]
    
    # Если номер без префикса, добавляем 380
    if len(digits) == 9:
        return '380' + digits
    
    return digits


async def topup_phone(phone: str, amount: float = 1.00):
    """Пополняет баланс телефона через Portmone API."""
    settings = get_settings()
    
    print("=" * 60)
    print("Тест пополнения телефона через Portmone Direct API")
    print("=" * 60)
    print()
    
    # Нормализуем номер телефона
    normalized_phone = normalize_phone(phone)
    print(f"Исходный номер: {phone}")
    print(f"Нормализованный номер: {normalized_phone}")
    print()
    
    # Проверяем конфигурацию
    print("Конфигурация:")
    print(f"  API Base URL: {settings.portmone_api_base}")
    print(f"  Login: {settings.portmone_login}")
    print(f"  Version: {settings.portmone_version}")
    print(f"  Payee ID: {settings.portmone_payee_id}")
    print(f"  Currency: {settings.portmone_default_currency}")
    print()
    
    # Определяем оператора по префиксу
    prefix = normalized_phone[3:5]  # Первые 2 цифры после 380
    operator = "Неизвестный"
    if prefix in ['39', '67', '68', '96', '97', '98']:
        operator = "Київстар"
    elif prefix in ['50', '66', '95', '99']:
        operator = "Vodafone Україна"
    elif prefix in ['63', '73', '93']:
        operator = "lifecell"
    
    print(f"Оператор: {operator} (префикс {prefix})")
    print(f"⚠️  Убедитесь, что PORTMONE_PAYEE_ID соответствует оператору {operator}")
    print()
    
    # Формируем payload для bills.create
    payload = {
        "payeeId": settings.portmone_payee_id,
        "contractNumber": normalized_phone,
        "amount": f"{amount:.2f}",
        "currency": settings.portmone_default_currency,
        "comment": f"Test top-up for {normalized_phone}",
    }
    
    print("Параметры запроса:")
    for key, value in payload.items():
        if key == "payeeId":
            print(f"  {key}: {value} (ID оператора)")
        else:
            print(f"  {key}: {value}")
    print()
    
    # Предупреждение
    print("⚠️  ВНИМАНИЕ: Это создаст РЕАЛЬНЫЙ счет на пополнение!")
    print("   Убедитесь, что:")
    print("   1. Учетные данные правильные")
    print("   2. PORTMONE_PAYEE_ID соответствует оператору")
    print("   3. Номер телефона правильный")
    print()
    
    response = input("Продолжить? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Отменено пользователем")
        return False
    
    print()
    print("Отправка запроса...")
    print()
    
    client = PortmoneDirectClient(settings)
    
    try:
        response = await client.call("bills.create", **payload)
        
        print("✅ Пополнение успешно инициировано!")
        print()
        print("Результат:")
        print(f"  Статус: {response.status}")
        print(f"  Bill ID: {response.bill_id}")
        print(f"  Contract Number: {response.contract_number}")
        
        if response.data:
            print()
            print("Дополнительные данные:")
            for key, value in list(response.data.items())[:10]:
                print(f"  {key}: {value}")
        
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
        print("  - Неверный payeeId (ID оператора)")
        print("  - Неверный формат номера телефона")
        print("  - Неверная сумма")
        print("  - Недостаточно прав доступа")
        return False
        
    except PortmoneError as e:
        print(f"❌ Неожиданная ошибка Portmone: {str(e)}")
        return False
        
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {type(e).__name__}: {str(e)}")
        return False
        
    finally:
        await client.aclose()


def main():
    """Главная функция."""
    phone = "0992227160"
    amount = 1.00
    
    print()
    print(f"Тест пополнения телефона {phone} на {amount} грн")
    print()
    
    success = asyncio.run(topup_phone(phone, amount))
    
    print()
    print("=" * 60)
    if success:
        print("✅ Тест завершен успешно")
        print()
        print("Примечание: Счет создан, но пополнение может занять некоторое время.")
        print("Проверьте статус через webhook или в личном кабинете Portmone.")
        sys.exit(0)
    else:
        print("❌ Тест завершен с ошибками")
        print()
        print("Проверьте:")
        print("  1. Учетные данные PORTMONE_LOGIN и PORTMONE_PASSWORD")
        print("  2. PORTMONE_PAYEE_ID соответствует оператору телефона")
        print("  3. Формат номера телефона (380XXXXXXXXX)")
        print("  4. Права доступа к API пополнения телефонов")
        sys.exit(1)


if __name__ == "__main__":
    main()

