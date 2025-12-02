#!/usr/bin/env python3
"""Скрипт для загрузки всех переменных окружения из Heroku в файл .env через Platform API"""

import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ Требуется библиотека requests. Установите: pip install requests", file=sys.stderr)
    sys.exit(1)

HEROKU_APP_NAME = "darnitsacashbot-b132719cee1f"


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


def get_heroku_config_via_api():
    """Получить переменные окружения из Heroku через Platform API"""
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
    
    # Получаем переменные окружения через API
    headers = {
        "Accept": "application/vnd.heroku+json; version=3",
        "Authorization": f"Bearer {api_token}",
    }
    
    url = f"https://api.heroku.com/apps/{HEROKU_APP_NAME}/config-vars"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        config_vars = response.json()
        
        # Форматируем в формат .env файла
        env_lines = []
        for key, value in sorted(config_vars.items()):
            # Экранируем специальные символы в значениях
            if "\n" in value or " " in value or "#" in value or "=" in value:
                # Используем кавычки для значений с пробелами или специальными символами
                env_lines.append(f'{key}="{value}"')
            else:
                env_lines.append(f"{key}={value}")
        
        return "\n".join(env_lines) + "\n"
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("❌ Неверный API токен. Проверьте токен и попробуйте снова.", file=sys.stderr)
        elif e.response.status_code == 404:
            print(f"❌ Приложение {HEROKU_APP_NAME} не найдено.", file=sys.stderr)
        else:
            print(f"❌ Ошибка API: {e}", file=sys.stderr)
            print(f"Ответ: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка при получении конфигурации: {e}", file=sys.stderr)
        sys.exit(1)


def save_to_env_file(content: str, env_path: Path):
    """Сохранить переменные окружения в файл .env"""
    # Очищаем пустые строки
    lines = [line for line in content.splitlines() if line.strip()]
    
    # Записываем в файл
    with open(env_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    
    print(f"✅ Сохранено {len(lines)} переменных окружения в {env_path}")


def main():
    """Основная функция"""
    print(f"Загрузка переменных окружения из Heroku приложения: {HEROKU_APP_NAME}")
    print("Используется Heroku Platform API\n")
    
    # Получаем конфигурацию
    config_content = get_heroku_config_via_api()
    
    if not config_content.strip():
        print("⚠️  Предупреждение: получена пустая конфигурация", file=sys.stderr)
        sys.exit(1)
    
    # Сохраняем в .env файл
    env_path = Path(".env")
    save_to_env_file(config_content, env_path)
    
    print(f"\n✅ Готово! Переменные окружения сохранены в {env_path.absolute()}")


if __name__ == "__main__":
    main()

