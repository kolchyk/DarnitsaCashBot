#!/usr/bin/env python3
"""Временный скрипт для проверки загрузки переменных из .env"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
import os

class TestSettings(BaseSettings):
    model_config = {"env_file": (".env", "env.example"), "env_file_encoding": "utf-8"}
    
    portmone_login: str = Field(default="demo_login", alias="PORTMONE_LOGIN")

# Проверяем напрямую из os
print("=== Проверка переменных окружения ===")
print(f"PORTMONE_LOGIN из os.getenv: {repr(os.getenv('PORTMONE_LOGIN'))}")

# Проверяем через pydantic-settings
settings = TestSettings()
print(f"PORTMONE_LOGIN из pydantic: {repr(settings.portmone_login)}")

# Проверяем чтение .env файла напрямую
env_file = Path(".env")
if env_file.exists():
    print(f"\n=== Содержимое .env файла (первые 20 строк) ===")
    with open(env_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 20:
                break
            if 'PORTMONE' in line.upper() or 'LOGIN' in line.upper():
                print(f"{i+1}: {line.rstrip()}")

