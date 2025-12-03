#!/usr/bin/env python3
"""
Тестовый скрипт для проверки запроса к API реестра фискальных чеков tax.gov.ua
Использование: python scripts/test_tax_api.py [url] [--token TOKEN]
"""
from __future__ import annotations

import sys
import json
import logging
import asyncio
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Добавляем корень проекта в путь
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


async def test_tax_api(url: str, token: str | None = None) -> None:
    """
    Тестирует запрос к API реестра фискальных чеков tax.gov.ua
    
    Args:
        url: URL чека из QR кода
        token: Токен авторизации (опционально, можно получить из настроек)
    """
    from apps.api_gateway.services.ocr.tax_api_client import (
        parse_receipt_url,
        fetch_receipt_data,
        TaxApiError
    )
    
    print("=" * 80)
    print("ТЕСТ ЗАПРОСА К API РЕЕСТРА ФИСКАЛЬНЫХ ЧЕКОВ")
    print("=" * 80)
    print(f"\n🔗 URL: {url}")
    print("-" * 80)
    
    # Шаг 1: Парсинг URL
    print("\n📋 ШАГ 1: Парсинг URL...")
    try:
        url_params = parse_receipt_url(url)
        print("✅ URL успешно распарсен!")
        print(f"   ID чека: {url_params.get('id')}")
        print(f"   Дата: {url_params.get('date')}")
        print(f"   Фіскальний номер РРО (fn): {url_params.get('fn')}")
    except Exception as e:
        print(f"❌ Ошибка при парсинге URL: {e}")
        return
    
    receipt_id = url_params.get("id")
    if not receipt_id:
        print("❌ Не удалось извлечь ID чека из URL")
        return
    
    # Шаг 2: Получение токена
    print("\n🔑 ШАГ 2: Получение токена авторизации...")
    if not token:
        try:
            from libs.common import get_settings
            settings = get_settings()
            token = settings.tax_gov_ua_api_token
        except Exception as e:
            print(f"⚠️  Не удалось загрузить токен из настроек: {e}")
            print("   Попробуйте передать токен через параметр --token")
            print("   Или установите переменную окружения TAX_GOV_UA_API_TOKEN")
            return
    
    if not token:
        print("❌ Токен не найден!")
        print("   Используйте: python scripts/test_tax_api.py <url> --token <token>")
        print("   Или установите переменную окружения TAX_GOV_UA_API_TOKEN")
        return
    
    print(f"✅ Токен получен: {token[:8]}..." if len(token) > 8 else "✅ Токен получен")
    
    # Шаг 3: Запрос к API
    print("\n🌐 ШАГ 3: Запрос к API...")
    print(f"   URL API: https://cabinet.tax.gov.ua/ws/api_public/rro/chkAll")
    print(f"   Метод: GET")
    print(f"   Параметры:")
    print(f"     - id: {receipt_id}")
    if url_params.get("date"):
        print(f"     - date: {url_params.get('date')}")
    if url_params.get("fn"):
        print(f"     - fn: {url_params.get('fn')}")
    print(f"     - type: 3 (текстовый формат)")
    
    try:
        api_response = await fetch_receipt_data(
            receipt_id=receipt_id,
            token=token,
            date=url_params.get("date"),
            fn=url_params.get("fn"),
            receipt_type=3,  # Text document for display (UTF-8)
        )
        
        print("\n" + "=" * 80)
        print("✅ ЗАПРОС УСПЕШЕН!")
        print("=" * 80)
        
        # Вывод ответа API
        print("\n📄 ОТВЕТ API:")
        print("-" * 80)
        
        # Основная информация
        if api_response.get("fn"):
            print(f"📋 Фіскальний номер РРО: {api_response['fn']}")
        
        if api_response.get("id"):
            print(f"🆔 Номер чека: {api_response['id']}")
        
        if api_response.get("name"):
            print(f"🏪 Торговельна точка: {api_response['name']}")
        
        # Данные чека
        check_data = api_response.get("check")
        if check_data:
            print(f"\n📄 Дані чека (довжина: {len(check_data)} символів):")
            print("-" * 80)
            # Показываем первые 500 символов
            preview = check_data[:500] if len(check_data) > 500 else check_data
            print(preview)
            if len(check_data) > 500:
                print(f"\n... (показано 500 з {len(check_data)} символів)")
            print("-" * 80)
        
        # XML данные
        xml_value = api_response.get("xml")
        if xml_value:
            if isinstance(xml_value, bool) and xml_value:
                print("\n✅ XML дані доступні")
            elif isinstance(xml_value, str) and xml_value:
                print(f"\n✅ XML дані доступні (довжина: {len(xml_value)} символів)")
        
        # Подпись
        sign_value = api_response.get("sign")
        if sign_value:
            if isinstance(sign_value, bool) and sign_value:
                print("✅ Чек підписано КЕП")
            elif isinstance(sign_value, str) and sign_value:
                print(f"✅ Чек підписано КЕП (довжина підпису: {len(sign_value)} символів)")
        
        # Сохранение полного ответа
        output_dir = PROJECT_ROOT / "scripts" / "test_results"
        output_dir.mkdir(exist_ok=True)
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = output_dir / f"tax_api_response_{timestamp}.json"
        
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(api_response, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 Повний відповідь збережено в: {json_file}")
        
        # Вывод всех ключей ответа для справки
        print("\n🔍 Структура відповіді API:")
        print("-" * 80)
        for key in sorted(api_response.keys()):
            value = api_response[key]
            if isinstance(value, str):
                preview = value[:100] if len(value) > 100 else value
                print(f"   📝 {key}: (рядок, {len(value)} символів)")
                if len(value) > 100:
                    print(f"      Попередній перегляд: {preview}...")
            elif isinstance(value, bool):
                print(f"   ✓ {key}: {value}")
            elif isinstance(value, (int, float)):
                print(f"   🔢 {key}: {value}")
            elif isinstance(value, dict):
                print(f"   📦 {key}: (словник з {len(value)} ключами)")
            elif isinstance(value, list):
                print(f"   📋 {key}: (список з {len(value)} елементами)")
            else:
                print(f"   ❓ {key}: {type(value).__name__}")
        
        # Проверка ожидаемых полей
        print("\n✅ Перевірка очікуваних полів:")
        expected_fields = ["check", "fn", "id", "name", "xml", "sign"]
        for field in expected_fields:
            if field in api_response:
                print(f"   ✅ {field}: присутнє")
            else:
                print(f"   ⚠️  {field}: відсутнє")
        
    except TaxApiError as e:
        print("\n" + "=" * 80)
        print("❌ ОШИБКА API")
        print("=" * 80)
        
        # Вывод детальной информации об ошибке
        status_code = getattr(e, 'status_code', None)
        error_description = getattr(e, 'error_description', None)
        
        print(f"\n📊 Деталі помилки:")
        if status_code:
            print(f"   Статус код: {status_code}")
        if error_description:
            print(f"   Опис помилки: {error_description}")
        print(f"   Повне повідомлення: {str(e)}")
        
        # Попытка получить raw response для анализа
        if hasattr(e, '__cause__') and hasattr(e.__cause__, 'response'):
            response = e.__cause__.response
            print(f"\n📄 Raw відповідь сервера:")
            print(f"   Статус: {response.status_code}")
            print(f"   Заголовки: {dict(response.headers)}")
            if response.text:
                print(f"   Тіло відповіді:")
                try:
                    error_json = response.json()
                    print(f"   {json.dumps(error_json, ensure_ascii=False, indent=2)}")
                except:
                    print(f"   {response.text[:500]}")
        
        # Сохранение ошибки для анализа
        output_dir = PROJECT_ROOT / "scripts" / "test_results"
        output_dir.mkdir(exist_ok=True)
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        error_file = output_dir / f"tax_api_error_{timestamp}.json"
        
        error_data = {
            "error": str(e),
            "status_code": status_code,
            "error_description": error_description,
            "url": url,
            "parsed_params": url_params if 'url_params' in locals() else None,
        }
        
        with open(error_file, "w", encoding="utf-8") as f:
            json.dump(error_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 Деталі помилки збережено в: {error_file}")
    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ НЕОЖИДАННАЯ ОШИБКА")
        print("=" * 80)
        print(f"\nТип ошибки: {type(e).__name__}")
        print(f"Сообщение: {str(e)}")
        print("\nПолный traceback:")
        import traceback
        traceback.print_exc()


def main() -> None:
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Тест запроса к API реестра фискальных чеков tax.gov.ua"
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="https://cabinet.tax.gov.ua/cashregs/check?id=UxI07gWmYOQ&date=20251201&time=16:12&fn=4001246197&sm=46.50",
        help="URL чека из QR кода"
    )
    parser.add_argument(
        "--token",
        help="Токен авторизации для API (опционально, можно использовать TAX_GOV_UA_API_TOKEN)"
    )
    
    args = parser.parse_args()
    
    # Запуск асинхронной функции
    asyncio.run(test_tax_api(args.url, args.token))
    
    print("\n" + "=" * 80)
    print("✅ Тест завершен")
    print("=" * 80)


if __name__ == "__main__":
    main()

