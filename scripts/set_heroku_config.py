#!/usr/bin/env python3
"""Скрипт для установки переменных окружения в Heroku через Platform API"""

import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ Требуется библиотека requests. Установите: pip install requests", file=sys.stderr)
    sys.exit(1)

# Попробуем найти имя приложения автоматически или использовать по умолчанию
HEROKU_APP_NAME = os.getenv("HEROKU_APP_NAME", "darnitsacashbot-b132719cee1f")


def get_heroku_api_token():
    """Получить Heroku API токен из переменной окружения или файла ~/.netrc"""
    # Сначала проверяем переменную окружения
    token = os.getenv("HEROKU_API_TOKEN")
    if token:
        return token
    
    # Пробуем прочитать из ~/.netrc (стандартное место для Heroku CLI)
    import platform
    if platform.system() == "Windows":
        netrc_path = Path.home() / "_netrc"
    else:
        netrc_path = Path.home() / ".netrc"
    
    if netrc_path.exists():
        try:
            import netrc
            nrc = netrc.netrc(netrc_path)
            # Ищем heroku.com в netrc
            for host, data in nrc.hosts.items():
                if "heroku" in host.lower():
                    return data[2]  # password field содержит API token
        except Exception:
            pass
    
    return None


def set_heroku_config_var(key: str, value: str):
    """Установить переменную окружения в Heroku через Platform API"""
    api_token = get_heroku_api_token()
    
    if not api_token:
        print("❌ Heroku API токен не найден", file=sys.stderr)
        print("\nПолучите токен одним из способов:", file=sys.stderr)
        print("  1. Через веб-интерфейс: https://dashboard.heroku.com/account", file=sys.stderr)
        print("  2. Через Heroku CLI: heroku auth:token", file=sys.stderr)
        print("\nЗатем установите переменную окружения:", file=sys.stderr)
        print("  set HEROKU_API_TOKEN=your_token_here  (Windows)", file=sys.stderr)
        print("  export HEROKU_API_TOKEN=your_token_here  (Linux/Mac)", file=sys.stderr)
        sys.exit(1)
    
    # Устанавливаем переменную окружения через API
    headers = {
        "Accept": "application/vnd.heroku+json; version=3",
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    
    url = f"https://api.heroku.com/apps/{HEROKU_APP_NAME}/config-vars"
    
    # Сначала получаем текущие переменные
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        config_vars = response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("❌ Неверный API токен. Проверьте токен и попробуйте снова.", file=sys.stderr)
        elif e.response.status_code == 404:
            print(f"❌ Приложение {HEROKU_APP_NAME} не найдено.", file=sys.stderr)
        else:
            print(f"❌ Ошибка API при получении конфигурации: {e}", file=sys.stderr)
            print(f"Ответ: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    
    # Добавляем новую переменную
    config_vars[key] = value
    
    # Обновляем конфигурацию
    try:
        response = requests.patch(url, headers=headers, json=config_vars)
        response.raise_for_status()
        print(f"✅ Переменная окружения {key} успешно установлена в Heroku приложении {HEROKU_APP_NAME}")
        return True
    except requests.exceptions.HTTPError as e:
        print(f"❌ Ошибка API при установке переменной: {e}", file=sys.stderr)
        print(f"Ответ: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка при установке переменной: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Основная функция"""
    if len(sys.argv) < 3:
        print("Использование: python scripts/set_heroku_config.py <KEY> <VALUE>")
        print("\nПример:")
        print("  python scripts/set_heroku_config.py TAX_GOV_UA_API_TOKEN f38dae70-5fe6-4e0a-a9c6-170713b7d79d")
        sys.exit(1)
    
    key = sys.argv[1]
    value = sys.argv[2]
    
    print(f"Установка переменной окружения {key} в Heroku приложении: {HEROKU_APP_NAME}")
    print("Используется Heroku Platform API\n")
    
    set_heroku_config_var(key, value)
    
    print(f"\n✅ Готово! Переменная {key} установлена в Heroku.")


if __name__ == "__main__":
    main()

