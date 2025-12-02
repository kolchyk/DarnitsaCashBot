#!/usr/bin/env python3
"""
Скрипт для тестирования пополнения счета через Portmone API.

Использование:
    python scripts/test_topup_phone.py
    
    # С указанием суммы
    python scripts/test_topup_phone.py --amount 10.00
    
    # С указанием номера телефона
    python scripts/test_topup_phone.py --phone 380992227160 --amount 5.00

Требуемые переменные окружения:
    - PORTMONE_LOGIN - логин компании-реселера
    - PORTMONE_PASSWORD - пароль компании-реселера
    - PORTMONE_API_BASE - базовый URL API (по умолчанию: https://direct.portmone.com.ua/api/directcash/)
    - PORTMONE_VERSION - версия протокола (по умолчанию: 2)
    - PORTMONE_PAYEE_ID_VODAFONE - ID оператора Vodafone (для номера 38099...)
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Устанавливаем минимальные переменные окружения для тестирования, если они не установлены
if not os.getenv("ENCRYPTION_SECRET"):
    os.environ["ENCRYPTION_SECRET"] = "test-secret-key-for-topup-testing-only"
if not os.getenv("TELEGRAM_BOT_TOKEN"):
    os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"

from libs.common.config import get_settings
from libs.common.portmone import (
    PortmoneDirectClient,
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


async def test_topup(phone_number: str, amount: float, use_mock: bool = False):
    """Тестирует пополнение счета через Portmone API."""
    print_header(f"Тестирование пополнения счета {phone_number}")
    
    settings = get_settings()
    
    # Переопределяем API base URL для mock-сервера
    if use_mock:
        original_base = settings.portmone_api_base
        settings.portmone_api_base = "http://localhost:8082/api/directcash/"
        print_info(f"Используется mock-сервер: {settings.portmone_api_base}")
        print_info(f"(Оригинальный URL: {original_base})")
        print()
    
    # Проверяем конфигурацию
    print_info("Проверка конфигурации:")
    print(f"   API Base URL: {settings.portmone_api_base}")
    print(f"   Login: {settings.portmone_login}")
    print(f"   Password: {'*' * len(settings.portmone_password) if settings.portmone_password else 'НЕ УСТАНОВЛЕН'}")
    print(f"   Version: {settings.portmone_version}")
    
    # Проверяем сертификат
    cert_display = "не указан"
    cert_exists = False
    if settings.portmone_cert_path:
        cert_path = Path(settings.portmone_cert_path)
        if cert_path.exists() and cert_path.is_file():
            cert_display = str(cert_path)
            cert_exists = True
        else:
            cert_display = f"{settings.portmone_cert_path} (файл не найден)"
    print(f"   Certificate: {cert_display}")
    
    if not cert_exists:
        print_warning("⚠️  SSL сертификат не найден!")
        print_warning("Portmone API требует клиентский SSL сертификат для аутентификации.")
        print_warning("Установите переменную окружения PORTMONE_CERT_PATH с путем к сертификату.")
        print()
    
    print()
    
    # Определяем оператора и payeeId
    payee_id = get_operator_payee_id(phone_number, settings)
    
    # Определяем оператора по префиксу
    prefix = phone_number[3:5] if len(phone_number) >= 5 else ""
    operator_name = "Неизвестный"
    if prefix in ['39', '67', '68', '96', '97', '98']:
        operator_name = "Київстар"
    elif prefix in ['50', '66', '95', '99']:
        operator_name = "Vodafone"
    elif prefix in ['63', '73', '93']:
        operator_name = "lifecell"
    
    print_info("Параметры пополнения:")
    print(f"   Номер телефона: {phone_number}")
    print(f"   Оператор: {operator_name}")
    print(f"   Payee ID: {payee_id}")
    print(f"   Сумма: {amount:.2f} {settings.portmone_default_currency}")
    print()
    
    # Проверяем наличие payeeId
    if not payee_id or payee_id == "100000":
        print_warning("Payee ID не установлен или использует значение по умолчанию!")
        print_warning("Убедитесь, что установлены переменные окружения:")
        if prefix in ['50', '66', '95', '99']:
            print_warning("   PORTMONE_PAYEE_ID_VODAFONE")
        elif prefix in ['39', '67', '68', '96', '97', '98']:
            print_warning("   PORTMONE_PAYEE_ID_KYIVSTAR")
        elif prefix in ['63', '73', '93']:
            print_warning("   PORTMONE_PAYEE_ID_LIFECELL")
        print_warning("   или PORTMONE_PAYEE_ID (общий)")
        print()
    
    # Проверяем учетные данные
    if not settings.portmone_login or settings.portmone_login == "demo_login":
        print_error("PORTMONE_LOGIN не установлен или использует значение по умолчанию!")
        print_error("Установите реальные учетные данные для тестирования")
        return False
    
    if not settings.portmone_password or settings.portmone_password == "demo_password":
        print_error("PORTMONE_PASSWORD не установлен или использует значение по умолчанию!")
        print_error("Установите реальные учетные данные для тестирования")
        return False
    
    # Проверяем, используется ли mock-сервер
    is_mock = use_mock or ("localhost" in settings.portmone_api_base or "127.0.0.1" in settings.portmone_api_base)
    if is_mock:
        print_info("Обнаружен mock-сервер (localhost)")
        print_info("Это тестовый запрос, реальный счет не будет создан")
    else:
        print_warning("Используется реальный API Portmone")
        print_warning("Это создаст реальный счет на пополнение!")
        print()
    
    # Форматируем сумму
    amount_str = f"{amount:.2f}"
    
    # Выполняем запрос
    import httpx
    from libs.common.portmone import parse_portmone_response
    
    client = PortmoneDirectClient(settings)
    
    try:
        print_info("Выполняем запрос: bills.create")
        print(f"   method=bills.create")
        print(f"   login={settings.portmone_login}")
        print(f"   payeeId={payee_id}")
        print(f"   contractNumber={phone_number}")
        print(f"   amount={amount_str}")
        print(f"   currency={settings.portmone_default_currency}")
        print()
        
        # Выполняем запрос напрямую для лучшей обработки ошибок
        payload = {
            "method": "bills.create",
            "login": settings.portmone_login,
            "password": settings.portmone_password,
            "version": settings.portmone_version,
            "payeeId": payee_id,
            "contractNumber": phone_number,
            "amount": amount_str,
            "currency": settings.portmone_default_currency,
            "comment": f"Test top-up for {phone_number}"
        }
        if settings.portmone_lang:
            payload["lang"] = settings.portmone_lang
        
        # Настраиваем клиент с сертификатом, если он указан
        cert = None
        if settings.portmone_cert_path:
            cert_path = Path(settings.portmone_cert_path)
            if cert_path.exists() and cert_path.is_file():
                cert = str(cert_path)
        
        async with httpx.AsyncClient(timeout=30.0, cert=cert) as http_client:
            response = await http_client.post(
                settings.portmone_api_base.rstrip("/") + "/",
                data=payload
            )
            
            print_info(f"HTTP статус: {response.status_code}")
            print_info(f"Ответ сервера:")
            print(f"   {response.text[:500]}")  # Первые 500 символов ответа
            print()
            
            if response.status_code != 200:
                print_error(f"HTTP ошибка {response.status_code}")
                print_error("Полный ответ:")
                print(response.text)
                
                if "No required SSL certificate" in response.text or "SSL certificate" in response.text:
                    print()
                    print_error("ТРЕБУЕТСЯ SSL СЕРТИФИКАТ!")
                    print_error("Portmone API требует клиентский SSL сертификат для аутентификации.")
                    print_error("Действия:")
                    print_error("   1. Получите сертификат от менеджера Portmone")
                    print_error("   2. Конвертируйте в формат PEM (если необходимо):")
                    print_error("      openssl pkcs12 -in certificate.pfx -out certificate.pem -nodes")
                    print_error("   3. Установите переменную окружения:")
                    print_error("      PORTMONE_CERT_PATH=/path/to/certificate.pem")
                
                return False
            
            # Парсим XML ответ
            parsed = parse_portmone_response(response.text)
            
            if parsed.status != "ok":
                print_error("API вернул ошибку при создании счета:")
                print(f"   Статус: {parsed.status}")
                print(f"   Raw XML: {parsed.raw}")
                if parsed.errors:
                    for error in parsed.errors:
                        print(f"   Код ошибки: {error.code}")
                        print(f"   Сообщение: {error.message}")
                        if error.description:
                            print(f"   Описание: {error.description}")
                return False
            
            print_success("Счет создан успешно!")
            print()
            print("Результат:")
            print(f"   Bill ID: {parsed.bill_id}")
            print(f"   Contract Number: {parsed.contract_number}")
            print(f"   Status: {parsed.status}")
            
            if parsed.data:
                print()
                print_info("Дополнительные данные из ответа:")
                for key, value in parsed.data.items():
                    print(f"   {key}: {value}")
            
            print()
            print_success("Пополнение счета инициировано успешно!")
            return True
        
    except PortmoneResponseError as e:
        print_error("API вернул ошибку при создании счета:")
        print(f"   Статус: {e.response.status}")
        print(f"   Raw XML: {e.response.raw}")
        if e.response.errors:
            for error in e.response.errors:
                print(f"   Код ошибки: {error.code}")
                print(f"   Сообщение: {error.message}")
                if error.description:
                    print(f"   Описание: {error.description}")
        return False
        
    except PortmoneTransportError as e:
        print_error(f"Ошибка транспорта (HTTP/TLS): {str(e)}")
        print_error("Проверьте:")
        print_error("   1. Подключение к интернету")
        print_error("   2. Правильность URL API")
        print_error("   3. Наличие сертификата (если требуется)")
        print_error("   4. Правильность учетных данных (LOGIN и PASSWORD)")
        return False
        
    except Exception as e:
        print_error(f"Неожиданная ошибка: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await client.aclose()


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description="Тестирование пополнения счета через Portmone API"
    )
    parser.add_argument(
        "--phone",
        type=str,
        default="380992227160",
        help="Номер телефона для пополнения (по умолчанию: 380992227160)"
    )
    parser.add_argument(
        "--amount",
        type=float,
        default=1.00,
        help="Сумма пополнения в UAH (по умолчанию: 1.00)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Использовать mock-сервер вместо реального API (http://localhost:8082/api/directcash/)"
    )
    
    args = parser.parse_args()
    
    # Валидация номера телефона
    phone = args.phone.strip()
    if not phone.startswith("380") or len(phone) != 12:
        print_error(f"Неверный формат номера телефона: {phone}")
        print_error("Номер должен быть в формате 380XXXXXXXXX (12 цифр)")
        sys.exit(1)
    
    # Валидация суммы
    if args.amount <= 0:
        print_error(f"Сумма должна быть положительной: {args.amount}")
        sys.exit(1)
    
    # Проверяем, запущен ли mock-сервер, если используется
    if args.mock:
        print_info("Используется mock-сервер для тестирования")
        print_info("Убедитесь, что mock-сервер запущен:")
        print_info("   python -m services.portmone_mock.main")
        print()
    
    # Запускаем тест
    success = asyncio.run(test_topup(phone, args.amount, use_mock=args.mock))
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

