#!/usr/bin/env python3
"""
Скрипт для проверки корректности конфигурации Cloudflare R2.

Проверяет:
- Наличие всех обязательных переменных окружения
- Формат endpoint URL
- Формат Account ID
- Формат Access Key и Secret Key
- Соответствие bucket name

Использование:
    python scripts/verify_r2_config.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from libs.common.config import get_settings


def validate_endpoint(endpoint: str | None) -> tuple[bool, str]:
    """Проверяет формат endpoint URL."""
    if not endpoint:
        return False, "Endpoint не установлен (должен быть указан для Cloudflare R2)"
    
    # Проверка формата Cloudflare R2 endpoint
    pattern = r'^https://[a-f0-9]{32}\.r2\.cloudflarestorage\.com$'
    if not re.match(pattern, endpoint):
        return False, f"Неверный формат endpoint URL: {endpoint}\nОжидается: https://<32-символьный-hex>.r2.cloudflarestorage.com"
    
    return True, "✅ Endpoint URL корректен"


def validate_account_id(endpoint: str) -> tuple[bool, str]:
    """Извлекает и проверяет Account ID из endpoint."""
    match = re.search(r'https://([a-f0-9]{32})\.r2\.cloudflarestorage\.com', endpoint)
    if not match:
        return False, "Не удалось извлечь Account ID из endpoint"
    
    account_id = match.group(1)
    return True, f"✅ Account ID: {account_id}"


def validate_access_key(access_key: str) -> tuple[bool, str]:
    """Проверяет формат Access Key."""
    if not access_key:
        return False, "Access Key не установлен"
    
    if len(access_key) < 16:
        return False, f"Access Key слишком короткий: {len(access_key)} символов (минимум 16)"
    
    return True, f"✅ Access Key: {access_key[:8]}... (длина: {len(access_key)})"


def validate_secret_key(secret_key: str) -> tuple[bool, str]:
    """Проверяет формат Secret Key."""
    if not secret_key:
        return False, "Secret Key не установлен"
    
    if len(secret_key) < 32:
        return False, f"Secret Key слишком короткий: {len(secret_key)} символов (минимум 32)"
    
    return True, f"✅ Secret Key: {secret_key[:8]}... (длина: {len(secret_key)})"


def validate_bucket_name(bucket: str) -> tuple[bool, str]:
    """Проверяет формат bucket name."""
    if not bucket:
        return False, "Bucket name не установлен"
    
    # S3 bucket naming rules
    if len(bucket) < 3 or len(bucket) > 63:
        return False, f"Bucket name должен быть от 3 до 63 символов (текущий: {len(bucket)})"
    
    if not re.match(r'^[a-z0-9][a-z0-9\-]*[a-z0-9]$', bucket):
        return False, "Bucket name должен содержать только строчные буквы, цифры и дефисы"
    
    return True, f"✅ Bucket name: {bucket}"


def validate_region(region: str) -> tuple[bool, str]:
    """Проверяет регион."""
    if not region:
        return False, "Region не установлен"
    
    valid_regions = ["auto", "EEUR", "WNAM", "ENAM", "APAC", "us-east-1", "us-west-1"]
    if region not in valid_regions:
        return False, f"Неизвестный регион: {region}\nВалидные значения: {', '.join(valid_regions)}"
    
    return True, f"✅ Region: {region}"


def main():
    """Главная функция проверки."""
    print("=" * 70)
    print("Проверка конфигурации Cloudflare R2")
    print("=" * 70)
    print()
    
    try:
        settings = get_settings()
    except Exception as e:
        print(f"❌ Ошибка при загрузке настроек: {e}")
        return 1
    
    all_valid = True
    checks = []
    
    # Проверка endpoint
    is_valid, message = validate_endpoint(settings.storage_endpoint)
    checks.append(("Endpoint URL", is_valid, message))
    if not is_valid:
        all_valid = False
    
    # Проверка Account ID (если endpoint валиден)
    if is_valid and settings.storage_endpoint:
        is_valid, message = validate_account_id(settings.storage_endpoint)
        checks.append(("Account ID", is_valid, message))
    
    # Проверка bucket
    is_valid, message = validate_bucket_name(settings.storage_bucket)
    checks.append(("Bucket Name", is_valid, message))
    if not is_valid:
        all_valid = False
    
    # Проверка Access Key
    is_valid, message = validate_access_key(settings.storage_access_key)
    checks.append(("Access Key", is_valid, message))
    if not is_valid:
        all_valid = False
    
    # Проверка Secret Key
    is_valid, message = validate_secret_key(settings.storage_secret_key)
    checks.append(("Secret Key", is_valid, message))
    if not is_valid:
        all_valid = False
    
    # Проверка Region
    is_valid, message = validate_region(settings.storage_region)
    checks.append(("Region", is_valid, message))
    if not is_valid:
        all_valid = False
    
    # Вывод результатов
    print("Результаты проверки:")
    print("-" * 70)
    for name, is_valid, message in checks:
        status = "✅" if is_valid else "❌"
        print(f"{status} {name}: {message}")
    print("-" * 70)
    print()
    
    # Сводка
    print("=" * 70)
    if all_valid:
        print("✅ Все проверки пройдены успешно!")
        print()
        print("Конфигурация Cloudflare R2:")
        print(f"  Endpoint: {settings.storage_endpoint}")
        print(f"  Bucket:   {settings.storage_bucket}")
        print(f"  Region:   {settings.storage_region}")
        print(f"  Access Key: {settings.storage_access_key[:8]}...")
        print()
        print("Следующий шаг: протестируйте подключение:")
        print("  python scripts/test_r2_local.py")
        return 0
    else:
        print("❌ Обнаружены ошибки в конфигурации!")
        print()
        print("Исправьте ошибки и повторите проверку.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

