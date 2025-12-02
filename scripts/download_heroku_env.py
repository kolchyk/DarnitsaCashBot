#!/usr/bin/env python3
"""Скрипт для загрузки всех переменных окружения из Heroku в файл .env"""

import subprocess
import sys
from pathlib import Path

HEROKU_APP_NAME = "darnitsacashbot"


def get_heroku_config():
    """Получить переменные окружения из Heroku"""
    import platform
    
    # Команды для попытки выполнения (сначала пробуем npx, так как heroku установлен через npm)
    commands = [
        f"npx --yes heroku config --app {HEROKU_APP_NAME} --shell",
        f"heroku config --app {HEROKU_APP_NAME} --shell",
    ]
    
    for cmd in commands:
        try:
            # Используем shell=True для Windows
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout.strip():
                return result.stdout
        except subprocess.CalledProcessError as e:
            # Продолжаем пробовать следующую команду
            continue
        except Exception as e:
            # Продолжаем пробовать следующую команду
            continue
    
    # Если ничего не сработало, выводим ошибку
    print("❌ Не удалось получить конфигурацию из Heroku", file=sys.stderr)
    print("Убедитесь, что:", file=sys.stderr)
    print("  1. Heroku CLI установлен (https://devcenter.heroku.com/articles/heroku-cli)", file=sys.stderr)
    print("  2. Выполнен вход: heroku login", file=sys.stderr)
    print("  3. Или используйте: npx heroku config --app <app-name> --shell", file=sys.stderr)
    sys.exit(1)


def save_to_env_file(content: str, env_path: Path):
    """Сохранить переменные окружения в файл .env"""
    # Очищаем пустые строки и лишние пробелы
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    
    # Записываем в файл
    with open(env_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    
    print(f"✅ Сохранено {len(lines)} переменных окружения в {env_path}")


def main():
    """Основная функция"""
    print(f"Загрузка переменных окружения из Heroku приложения: {HEROKU_APP_NAME}")
    
    # Получаем конфигурацию
    config_content = get_heroku_config()
    
    if not config_content.strip():
        print("⚠️  Предупреждение: получена пустая конфигурация", file=sys.stderr)
        print("Возможно, требуется аутентификация в Heroku CLI", file=sys.stderr)
        print("Выполните: heroku login", file=sys.stderr)
        sys.exit(1)
    
    # Сохраняем в .env файл
    env_path = Path(".env")
    save_to_env_file(config_content, env_path)
    
    print(f"\n✅ Готово! Переменные окружения сохранены в {env_path.absolute()}")


if __name__ == "__main__":
    main()

