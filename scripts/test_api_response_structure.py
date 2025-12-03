#!/usr/bin/env python3
"""
Скрипт для проверки структуры ответа API и обработки данных
Проверяет, как код обрабатывает различные варианты ответов от API
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def test_response_processing():
    """Тестирует обработку различных вариантов ответов API"""
    
    print("=" * 80)
    print("ТЕСТ ОБРАБОТКИ СТРУКТУРИ ОТВЕТА API")
    print("=" * 80)
    
    # Пример успешного ответа (на основе документации API)
    success_response_example = {
        "id": "UxI07gWmYOQ",
        "fn": "4001246197",
        "name": "ТОВ \"Приклад\"",
        "check": """ФІСКАЛЬНИЙ ЧЕК
ТОВ "Приклад"
Адреса: вул. Прикладна, 1
Тел: +380123456789

Чек № 12345
Дата: 01.12.2025 16:12:00
ФН РРО: 4001246197

Товар 1                   50.00
Товар 2                   100.00
------------------------
Всього:                  150.00
""",
        "xml": True,  # или может быть строка с XML
        "sign": True,  # или может быть строка с подписью
    }
    
    # Пример ответа с ошибкой
    error_response_example = {
        "error": "Помилка",
        "error_description": "Помилка перевірки На період дії воєнного стану обмежено доступ до публічних електронних реєстрів\""
    }
    
    print("\n📋 ТЕСТ 1: Обработка успешного ответа")
    print("-" * 80)
    test_success_response(success_response_example)
    
    print("\n📋 ТЕСТ 2: Обработка ответа с ошибкой")
    print("-" * 80)
    test_error_response(error_response_example)
    
    print("\n📋 ТЕСТ 3: Проверка функции форматирования сообщения")
    print("-" * 80)
    test_message_formatting(success_response_example)


def test_success_response(response: dict):
    """Тестирует обработку успешного ответа"""
    
    print("✅ Проверка полей успешного ответа:")
    
    # Проверка обязательных/ожидаемых полей
    expected_fields = {
        "id": "Номер чека",
        "fn": "Фіскальний номер РРО",
        "check": "Дані чека (текст)",
    }
    
    optional_fields = {
        "name": "Назва торговельної точки",
        "xml": "XML дані",
        "sign": "Підпис КЕП",
    }
    
    for field, description in expected_fields.items():
        if field in response:
            value = response[field]
            print(f"   ✅ {field} ({description}): присутнє")
            if isinstance(value, str):
                print(f"      Довжина: {len(value)} символів")
                if len(value) > 50:
                    print(f"      Попередній перегляд: {value[:50]}...")
        else:
            print(f"   ⚠️  {field} ({description}): відсутнє")
    
    for field, description in optional_fields.items():
        if field in response:
            value = response[field]
            print(f"   ℹ️  {field} ({description}): присутнє")
            if isinstance(value, bool):
                print(f"      Значення: {value}")
            elif isinstance(value, str):
                print(f"      Довжина: {len(value)} символів")
        else:
            print(f"   ℹ️  {field} ({description}): відсутнє (опціонально)")


def test_error_response(response: dict):
    """Тестирует обработку ответа с ошибкой"""
    
    print("✅ Проверка полей ответа с ошибкой:")
    
    if "error" in response:
        print(f"   ✅ error: {response['error']}")
    
    if "error_description" in response:
        print(f"   ✅ error_description: {response['error_description']}")
    
    # Проверка обработки ошибки военного времени
    error_desc = response.get("error_description", "")
    if "воєнн" in error_desc.lower() or "обмежено доступ" in error_desc.lower():
        print("   ✅ Обнаружена ошибка ограничения военного времени")
        print("   💡 Код должен обработать это специальным образом")


def test_message_formatting(response: dict):
    """Тестирует форматирование сообщения для пользователя"""
    
    print("✅ Тест форматирования сообщения:")
    
    # Симуляция функции форматирования
    message_parts = ["✅ <b>Дані чека отримано з реєстру фіскальних чеків</b>\n\n"]
    
    # Добавление полей
    if response.get("fn"):
        message_parts.append(f"📋 <b>Фіскальний номер РРО:</b> {response['fn']}\n\n")
    
    if response.get("id"):
        message_parts.append(f"🆔 <b>Номер чека:</b> {response['id']}\n\n")
    
    if response.get("name"):
        message_parts.append(f"🏪 <b>Торговельна точка:</b> {response['name']}\n\n")
    
    check_data = response.get("check")
    if check_data and isinstance(check_data, str):
        message_parts.append("📄 <b>Дані чека:</b>\n")
        message_parts.append("<pre>")
        # Ограничение длины для Telegram (4096 символов)
        max_length = 3500
        check_preview = check_data[:max_length] if len(check_data) > max_length else check_data
        message_parts.append(check_preview)
        if len(check_data) > max_length:
            message_parts.append("\n\n... (текст обрізано через обмеження Telegram)")
        message_parts.append("</pre>\n\n")
    
    xml_value = response.get("xml")
    if xml_value:
        if isinstance(xml_value, bool) and xml_value:
            message_parts.append("✅ XML дані доступні\n\n")
        elif isinstance(xml_value, str) and xml_value:
            message_parts.append("✅ XML дані доступні\n\n")
    
    sign_value = response.get("sign")
    if sign_value:
        if isinstance(sign_value, bool) and sign_value:
            message_parts.append("✅ Чек підписано КЕП\n\n")
        elif isinstance(sign_value, str) and sign_value:
            message_parts.append("✅ Чек підписано КЕП\n\n")
    
    message = "".join(message_parts)
    
    print(f"   Довжина повідомлення: {len(message)} символів")
    print(f"   Ліміт Telegram: 4096 символів")
    
    if len(message) > 4096:
        print("   ⚠️  ПОВІДОМЛЕННЯ ПЕРЕВИЩУЄ ЛІМІТ!")
        print(f"   Потрібно обрізати на {len(message) - 4096} символів")
    else:
        print(f"   ✅ Повідомлення в межах ліміту (залишилось {4096 - len(message)} символів)")
    
    # Показываем первые 200 символов сообщения
    print(f"\n   Попередній перегляд повідомлення:")
    print(f"   {message[:200]}...")


if __name__ == "__main__":
    test_response_processing()
    print("\n" + "=" * 80)
    print("✅ Тест завершен")
    print("=" * 80)

