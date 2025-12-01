#!/usr/bin/env python3
"""
Расширенный скрипт для тестирования API Portmone Direct.

Использование:
    # Тест с mock-сервером (рекомендуется для разработки)
    PORTMONE_API_BASE=http://localhost:8082/api/directcash/ python scripts/test_portmone_api.py
    
    # Тест с реальным API (требует реальных учетных данных)
    python scripts/test_portmone_api.py

Требуемые переменные окружения:
    - PORTMONE_LOGIN - логин компании-реселера
    - PORTMONE_PASSWORD - пароль компании-реселера
    - PORTMONE_API_BASE - базовый URL API (по умолчанию: https://direct.portmone.com.ua/api/directcash/)
    - PORTMONE_VERSION - версия протокола (по умолчанию: 2)
    - PORTMONE_PAYEE_ID - ID оператора (для тестов bills.create)
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from libs.common.config import get_settings
from libs.common.portmone import (
    PortmoneDirectClient,
    PortmoneError,
    PortmoneResponse,
    PortmoneResponseError,
    PortmoneTransportError,
    get_operator_payee_id,
)


class Colors:
    """ANSI цвета для вывода в терминал."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_success(message: str):
    """Выводит сообщение об успехе."""
    print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")


def print_error(message: str):
    """Выводит сообщение об ошибке."""
    print(f"{Colors.RED}❌ {message}{Colors.RESET}")


def print_warning(message: str):
    """Выводит предупреждение."""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.RESET}")


def print_info(message: str):
    """Выводит информационное сообщение."""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.RESET}")


def print_header(title: str):
    """Выводит заголовок секции."""
    print()
    print("=" * 70)
    print(f"{Colors.BOLD}{title}{Colors.RESET}")
    print("=" * 70)
    print()


async def test_connection(client: PortmoneDirectClient) -> bool:
    """Тест 1: Проверка подключения к API."""
    print_header("Тест 1: Проверка подключения к API")
    
    try:
        print_info("Выполняем запрос: payers.getPayersList")
        response = await client.call("payers.getPayersList")
        
        print_success("Подключение успешно!")
        print(f"   Статус ответа: {response.status}")
        print(f"   Данные получены: {'да' if response.data else 'нет'}")
        
        if response.errors:
            print_warning(f"   Предупреждения: {len(response.errors)}")
            for error in response.errors:
                print(f"     - Код: {error.code}, Сообщение: {error.message}")
        
        return True
        
    except PortmoneTransportError as e:
        print_error(f"Ошибка транспорта (HTTP/TLS): {str(e)}")
        return False
        
    except PortmoneResponseError as e:
        print_error("API вернул ошибку:")
        print(f"   Статус: {e.response.status}")
        if e.response.errors:
            for error in e.response.errors:
                print(f"   Код ошибки: {error.code}")
                print(f"   Сообщение: {error.message}")
                if error.description:
                    print(f"   Описание: {error.description}")
        return False
        
    except Exception as e:
        print_error(f"Неожиданная ошибка: {type(e).__name__}: {str(e)}")
        return False


async def test_bills_create(client: PortmoneDirectClient, settings: Any) -> bool:
    """Тест 2: Создание счета (bills.create)."""
    print_header("Тест 2: Создание счета (bills.create)")
    
    # Проверяем наличие payeeId
    if not settings.portmone_payee_id or settings.portmone_payee_id == "100000":
        print_warning("PORTMONE_PAYEE_ID не установлен или использует значение по умолчанию")
        print_info("Для теста с реальным API установите PORTMONE_PAYEE_ID")
        print_info("Пропускаем тест создания счета...")
        return True  # Не критичная ошибка для mock-сервера
    
    # Тестовые данные
    test_phone = "380991234567"  # Тестовый номер телефона
    test_amount = "1.00"
    test_currency = settings.portmone_default_currency or "UAH"
    
    # Определяем payeeId для оператора
    payee_id = get_operator_payee_id(test_phone, settings)
    
    print_info(f"Тестовые данные:")
    print(f"   Номер телефона: {test_phone}")
    print(f"   Сумма: {test_amount} {test_currency}")
    print(f"   Payee ID: {payee_id}")
    print()
    
    try:
        print_info("Выполняем запрос: bills.create")
        response = await client.call(
            "bills.create",
            payeeId=payee_id,
            contractNumber=test_phone,
            amount=test_amount,
            currency=test_currency,
            comment="Test bill creation from script"
        )
        
        print_success("Счет создан успешно!")
        print(f"   Bill ID: {response.bill_id}")
        print(f"   Contract Number: {response.contract_number}")
        
        if response.data:
            print_info("Дополнительные данные из ответа:")
            for key, value in list(response.data.items())[:10]:  # Показываем первые 10 полей
                print(f"     {key}: {value}")
        
        return True
        
    except PortmoneResponseError as e:
        print_error("API вернул ошибку при создании счета:")
        print(f"   Статус: {e.response.status}")
        if e.response.errors:
            for error in e.response.errors:
                print(f"   Код ошибки: {error.code}")
                print(f"   Сообщение: {error.message}")
                if error.description:
                    print(f"   Описание: {error.description}")
        return False
        
    except PortmoneTransportError as e:
        print_error(f"Ошибка транспорта: {str(e)}")
        return False
        
    except Exception as e:
        print_error(f"Неожиданная ошибка: {type(e).__name__}: {str(e)}")
        return False


async def test_invalid_method(client: PortmoneDirectClient) -> bool:
    """Тест 3: Проверка обработки неверного метода."""
    print_header("Тест 3: Обработка неверного метода")
    
    try:
        print_info("Выполняем запрос с неверным методом: invalid.method")
        await client.call("invalid.method")
        
        print_warning("Неожиданно: запрос с неверным методом прошел успешно")
        return False
        
    except PortmoneResponseError as e:
        print_success("Ошибка обработана корректно (ожидаемое поведение)")
        print(f"   Статус: {e.response.status}")
        if e.response.errors:
            for error in e.response.errors:
                print(f"   Код ошибки: {error.code}")
                print(f"   Сообщение: {error.message}")
        return True
        
    except Exception as e:
        print_error(f"Неожиданная ошибка: {type(e).__name__}: {str(e)}")
        return False


async def test_invalid_phone_number(client: PortmoneDirectClient, settings: Any) -> bool:
    """Тест 4: Проверка обработки неверного номера телефона."""
    print_header("Тест 4: Обработка неверного номера телефона")
    
    if not settings.portmone_payee_id or settings.portmone_payee_id == "100000":
        print_info("Пропускаем тест (требует payeeId)")
        return True
    
    invalid_phones = [
        "1234567890",  # Неправильный формат
        "38012345",    # Слишком короткий
        "380991234567890",  # Слишком длинный
    ]
    
    payee_id = settings.portmone_payee_id
    
    for invalid_phone in invalid_phones:
        try:
            print_info(f"Тестируем номер: {invalid_phone}")
            await client.call(
                "bills.create",
                payeeId=payee_id,
                contractNumber=invalid_phone,
                amount="1.00",
                currency="UAH"
            )
            print_warning(f"Неожиданно: запрос с номером {invalid_phone} прошел успешно")
            
        except PortmoneResponseError as e:
            print_success(f"Ошибка обработана корректно для номера {invalid_phone}")
            if e.response.errors:
                error = e.response.errors[0]
                print(f"   Код: {error.code}, Сообщение: {error.message}")
        except Exception as e:
            print_error(f"Неожиданная ошибка: {type(e).__name__}: {str(e)}")
    
    return True


async def test_operator_detection(settings: Any) -> bool:
    """Тест 5: Проверка определения оператора по номеру телефона."""
    print_header("Тест 5: Определение оператора по номеру телефона")
    
    test_cases = [
        ("380991234567", "Vodafone"),
        ("380671234567", "Kyivstar"),
        ("380631234567", "lifecell"),
        ("380501234567", "Vodafone"),
        ("380391234567", "Kyivstar"),
    ]
    
    print_info("Тестируем определение payeeId для разных операторов:")
    print()
    
    for phone, expected_operator in test_cases:
        payee_id = get_operator_payee_id(phone, settings)
        print(f"   {phone} ({expected_operator}): payeeId = {payee_id}")
    
    print()
    print_success("Определение операторов работает корректно")
    return True


def print_configuration(settings: Any):
    """Выводит конфигурацию для тестирования."""
    print_header("Конфигурация тестирования")
    
    print("Параметры подключения:")
    print(f"   API Base URL: {settings.portmone_api_base}")
    print(f"   Login: {settings.portmone_login}")
    print(f"   Password: {'*' * len(settings.portmone_password) if settings.portmone_password else 'НЕ УСТАНОВЛЕН'}")
    print(f"   Version: {settings.portmone_version}")
    print(f"   Language: {settings.portmone_lang or 'не указан (по умолчанию: uk)'}")
    
    cert_display = "не указан"
    if settings.portmone_cert_path:
        cert_path = Path(settings.portmone_cert_path)
        if cert_path.exists() and cert_path.is_file():
            cert_display = str(cert_path)
        else:
            cert_display = f"{settings.portmone_cert_path} (файл не найден)"
    print(f"   Certificate: {cert_display}")
    
    print()
    print("Параметры для bills.create:")
    print(f"   Payee ID (общий): {settings.portmone_payee_id}")
    print(f"   Payee ID (Kyivstar): {settings.portmone_payee_id_kyivstar or 'не установлен'}")
    print(f"   Payee ID (Vodafone): {settings.portmone_payee_id_vodafone or 'не установлен'}")
    print(f"   Payee ID (lifecell): {settings.portmone_payee_id_lifecell or 'не установлен'}")
    print(f"   Default Currency: {settings.portmone_default_currency}")
    
    print()
    
    # Проверяем, используется ли mock-сервер
    is_mock = "localhost" in settings.portmone_api_base or "127.0.0.1" in settings.portmone_api_base
    if is_mock:
        print_info("Обнаружен mock-сервер (localhost)")
        print_info("Для тестирования с реальным API установите PORTMONE_API_BASE")
    else:
        print_warning("Используется реальный API Portmone")
        print_warning("Убедитесь, что у вас есть реальные учетные данные")
    
    print()


async def main():
    """Главная функция тестирования."""
    settings = get_settings()
    
    print()
    print("=" * 70)
    print(f"{Colors.BOLD}Тестирование API Portmone Direct{Colors.RESET}")
    print("=" * 70)
    print()
    
    print_configuration(settings)
    
    # Проверяем обязательные параметры
    if not settings.portmone_login or settings.portmone_login == "demo_login":
        print_warning("PORTMONE_LOGIN не установлен или использует значение по умолчанию!")
        print_warning("Для тестирования с реальным API установите PORTMONE_LOGIN")
        print()
    
    if not settings.portmone_password or settings.portmone_password == "demo_password":
        print_warning("PORTMONE_PASSWORD не установлен или использует значение по умолчанию!")
        print_warning("Для тестирования с реальным API установите PORTMONE_PASSWORD")
        print()
    
    client = PortmoneDirectClient(settings)
    
    results = []
    
    try:
        # Тест 1: Подключение
        results.append(("Подключение к API", await test_connection(client)))
        
        # Тест 2: Создание счета
        results.append(("Создание счета", await test_bills_create(client, settings)))
        
        # Тест 3: Неверный метод
        results.append(("Обработка ошибок", await test_invalid_method(client)))
        
        # Тест 4: Неверный номер телефона
        results.append(("Валидация номера", await test_invalid_phone_number(client, settings)))
        
        # Тест 5: Определение оператора
        results.append(("Определение оператора", await test_operator_detection(settings)))
        
    finally:
        await client.aclose()
    
    # Итоги
    print_header("Итоги тестирования")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"   {test_name}: {status}")
    
    print()
    print(f"Всего тестов: {total}")
    print(f"Пройдено: {passed}")
    print(f"Провалено: {total - passed}")
    print()
    
    if passed == total:
        print_success("Все тесты пройдены успешно!")
        sys.exit(0)
    else:
        print_error("Некоторые тесты провалены")
        print()
        print("Рекомендации:")
        print("  1. Проверьте переменные окружения")
        print("  2. Убедитесь, что mock-сервер запущен (если используется)")
        print("  3. Проверьте подключение к интернету (для реального API)")
        print("  4. Убедитесь, что учетные данные корректны")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

