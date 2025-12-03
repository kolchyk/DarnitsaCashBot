#!/usr/bin/env python3
"""
Тестовый скрипт для проверки форматирования сообщения пользователю с ответом API
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def format_api_response_message(api_response: dict) -> str:
    """Форматирует ответ API в сообщение для пользователя (копия логики из worker.py)"""
    
    message_parts = ["✅ <b>Дані чека отримано з реєстру фіскальних чеків</b>\n\n"]
    message_parts.append("━━━━━━━━━━━━━━━━━━━━\n\n")
    
    # Add merchant name if available (most important info first)
    merchant_name = api_response.get("name")
    if merchant_name:
        message_parts.append(f"🏪 <b>Торговельна точка:</b> {merchant_name}\n\n")
    
    # Add receipt ID if available
    receipt_api_id = api_response.get("id")
    if receipt_api_id:
        message_parts.append(f"🆔 <b>Номер чека:</b> {receipt_api_id}\n\n")
    
    # Add fiscal number if available
    fn_value = api_response.get("fn")
    if fn_value:
        message_parts.append(f"📋 <b>Фіскальний номер РРО:</b> {fn_value}\n\n")
    
    message_parts.append("━━━━━━━━━━━━━━━━━━━━\n\n")
    
    # Add check data (text receipt) if available
    check_data = api_response.get("check")
    if check_data and isinstance(check_data, str):
        message_parts.append("📄 <b>Дані чека:</b>\n")
        message_parts.append("<pre>")
        # Calculate available space (Telegram limit is 4096 characters, reserve ~500 for other content)
        available_space = 3500
        # Count current message length
        current_length = len("".join(message_parts))
        remaining_space = available_space - current_length
        
        if remaining_space > 100:
            # Escape HTML special characters in check data for <pre> tag
            check_preview = check_data[:remaining_space - 50] if len(check_data) > remaining_space - 50 else check_data
            # Replace HTML entities that might break the message
            check_preview = check_preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            message_parts.append(check_preview)
            if len(check_data) > remaining_space - 50:
                message_parts.append("\n\n... (текст обрізано через обмеження Telegram)")
        else:
            message_parts.append("(текст чека занадто великий для відображення)")
        
        message_parts.append("</pre>\n\n")
    
    # Add additional info section
    has_additional_info = False
    info_parts = []
    
    # Add XML availability info
    xml_value = api_response.get("xml")
    if xml_value:
        if isinstance(xml_value, bool) and xml_value:
            info_parts.append("✅ XML дані доступні")
            has_additional_info = True
        elif isinstance(xml_value, str) and xml_value:
            info_parts.append("✅ XML дані доступні")
            has_additional_info = True
    
    # Add signature info
    sign_value = api_response.get("sign")
    if sign_value:
        if isinstance(sign_value, bool) and sign_value:
            info_parts.append("✅ Чек підписано КЕП")
            has_additional_info = True
        elif isinstance(sign_value, str) and sign_value:
            info_parts.append("✅ Чек підписано КЕП")
            has_additional_info = True
    
    if has_additional_info:
        message_parts.append("📌 <b>Додаткова інформація:</b>\n")
        message_parts.append("\n".join(info_parts))
        message_parts.append("\n\n")
    
    message = "".join(message_parts)
    
    # Ensure message doesn't exceed Telegram limit
    if len(message) > 4096:
        # Truncate message and add note
        message = message[:4000] + "\n\n... (повідомлення обрізано)"
    
    return message


def main():
    """Тестирует форматирование сообщения"""
    
    print("=" * 80)
    print("ТЕСТ ФОРМАТУВАННЯ ПОВІДОМЛЕННЯ КОРИСТУВАЧУ")
    print("=" * 80)
    
    # Пример успешного ответа API
    api_response = {
        "id": "UxI07gWmYOQ",
        "fn": "4001246197",
        "name": "ТОВ \"Аптека Дарниця\"",
        "check": """ФІСКАЛЬНИЙ ЧЕК
ТОВ "Аптека Дарниця"
Адреса: вул. Хрещатик, 1, м. Київ
Тел: +380441234567

Чек № 12345
Дата: 01.12.2025 16:12:00
ФН РРО: 4001246197

Дарниця Цитрамон           25.50
Дарниця Аспірин            30.00
Вода мінеральна            15.00
------------------------
Всього:                    70.50
Готівка:                   70.50
Решта:                       0.00

Дякуємо за покупку!
""",
        "xml": True,
        "sign": True,
    }
    
    print("\n📋 Вхідні дані API:")
    print("-" * 80)
    print(f"ID чека: {api_response.get('id')}")
    print(f"ФН РРО: {api_response.get('fn')}")
    print(f"Торговельна точка: {api_response.get('name')}")
    print(f"Довжина тексту чека: {len(api_response.get('check', ''))} символів")
    print(f"XML доступний: {api_response.get('xml')}")
    print(f"Підпис КЕП: {api_response.get('sign')}")
    
    print("\n📨 Сформоване повідомлення:")
    print("=" * 80)
    message = format_api_response_message(api_response)
    print(message)
    print("=" * 80)
    
    print(f"\n📊 Статистика повідомлення:")
    print(f"   Довжина: {len(message)} символів")
    print(f"   Ліміт Telegram: 4096 символів")
    if len(message) <= 4096:
        print(f"   ✅ Повідомлення в межах ліміту (залишилось {4096 - len(message)} символів)")
    else:
        print(f"   ⚠️  Повідомлення перевищує ліміт на {len(message) - 4096} символів")
    
    # Сохранение примера сообщения
    output_dir = Path(PROJECT_ROOT) / "scripts" / "test_results"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "example_user_message.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("ПРИКЛАД ПОВІДОМЛЕННЯ КОРИСТУВАЧУ З ВІДПОВІДДЮ API\n")
        f.write("=" * 80 + "\n\n")
        f.write(message)
        f.write("\n\n" + "=" * 80 + "\n")
        f.write(f"Довжина: {len(message)} символів\n")
    
    print(f"\n💾 Приклад збережено в: {output_file}")
    
    print("\n" + "=" * 80)
    print("✅ Тест завершено")
    print("=" * 80)


if __name__ == "__main__":
    main()

