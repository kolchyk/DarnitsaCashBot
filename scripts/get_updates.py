#!/usr/bin/env python3
"""Получить последние события бота через Telegram Bot API getUpdates."""

import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Сначала пробуем получить токен из переменной окружения
token = os.getenv("TELEGRAM_BOT_TOKEN")

# Если не найден, пробуем загрузить через настройки проекта
if not token:
    try:
        from libs.common import get_settings
        settings = get_settings()
        token = settings.telegram_bot_token
    except Exception as e:
        print(f"Предупреждение: не удалось загрузить настройки: {e}")
        print("Попробуйте установить переменную окружения TELEGRAM_BOT_TOKEN")
        sys.exit(1)

if not token:
    print("Ошибка: TELEGRAM_BOT_TOKEN не найден")
    print("Установите переменную окружения: export TELEGRAM_BOT_TOKEN=your_token")
    sys.exit(1)

# Telegram Bot API endpoint
base_url = f"https://api.telegram.org/bot{token}/getUpdates"

# Параметры запроса (можно настроить)
params = {
    "offset": 0,  # Начать с начала (0 = все недавние)
    "limit": 100,  # Максимум 100 обновлений
    "timeout": 0,  # Не ждать новых обновлений
}

# Формируем полный URL с параметрами
url = f"{base_url}?{urlencode(params)}"

print(f"Запрос к Telegram Bot API...")
print(f"URL: https://api.telegram.org/bot{token[:10]}.../getUpdates")
print()

try:
    with urlopen(url, timeout=10) as response:
        response_data = response.read().decode('utf-8')
        data = json.loads(response_data)
    
    if not data.get("ok"):
        print(f"Ошибка API: {data.get('description', 'Unknown error')}")
        sys.exit(1)
    
    updates = data.get("result", [])
    
    print(f"Получено обновлений: {len(updates)}")
    print("=" * 80)
    
    if not updates:
        print("Нет новых обновлений.")
    else:
        # Красиво выводим каждое обновление
        for i, update in enumerate(updates, 1):
            print(f"\n--- Обновление #{i} (update_id: {update.get('update_id')}) ---")
            
            # Сообщение
            if "message" in update:
                msg = update["message"]
                print(f"Тип: Сообщение")
                print(f"  ID сообщения: {msg.get('message_id')}")
                print(f"  От: {msg.get('from', {}).get('first_name', 'Unknown')} (@{msg.get('from', {}).get('username', 'N/A')})")
                print(f"  Chat ID: {msg.get('chat', {}).get('id')}")
                print(f"  Дата: {msg.get('date')}")
                if "text" in msg:
                    print(f"  Текст: {msg['text']}")
                if "photo" in msg:
                    print(f"  Фото: {len(msg['photo'])} вариантов")
                if "document" in msg:
                    print(f"  Документ: {msg['document'].get('file_name', 'N/A')}")
            
            # Редактирование сообщения
            elif "edited_message" in update:
                msg = update["edited_message"]
                print(f"Тип: Редактированное сообщение")
                print(f"  ID сообщения: {msg.get('message_id')}")
                print(f"  От: {msg.get('from', {}).get('first_name', 'Unknown')}")
                if "text" in msg:
                    print(f"  Текст: {msg['text']}")
            
            # Callback query
            elif "callback_query" in update:
                cb = update["callback_query"]
                print(f"Тип: Callback Query")
                print(f"  ID: {cb.get('id')}")
                print(f"  От: {cb.get('from', {}).get('first_name', 'Unknown')}")
                print(f"  Данные: {cb.get('data', 'N/A')}")
            
            # Другие типы обновлений
            else:
                print(f"Тип: {list(update.keys())[0] if update.keys() else 'Unknown'}")
                print(f"  Данные: {json.dumps(update, indent=2, ensure_ascii=False)}")
        
        print("\n" + "=" * 80)
        print(f"\nВсего обновлений: {len(updates)}")
        print(f"Последний update_id: {updates[-1].get('update_id')}")
        
        # Сохраняем в файл для удобства
        output_file = project_root / "scripts" / "last_updates.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\nПолные данные сохранены в: {output_file}")

except HTTPError as e:
    print(f"Ошибка HTTP при запросе к API: {e.code} - {e.reason}")
    try:
        error_body = e.read().decode('utf-8')
        print(f"Детали: {error_body}")
    except:
        pass
    sys.exit(1)
except URLError as e:
    print(f"Ошибка при запросе к API: {e.reason}")
    sys.exit(1)
except Exception as e:
    print(f"Неожиданная ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

