#!/usr/bin/env python3
"""Проверка чтения значений с кавычками из .env"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class TestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')
    login: str = Field(default='', alias='PORTMONE_LOGIN')
    password: str = Field(default='', alias='PORTMONE_PASSWORD')

s = TestSettings()
print('Login:', repr(s.login))
print('Password:', repr(s.password))
print('Login length:', len(s.login))
print('Password length:', len(s.password))

# Проверяем, есть ли кавычки в значениях
if s.login.startswith('"') and s.login.endswith('"'):
    print('\n⚠️  ВНИМАНИЕ: Login содержит кавычки!')
    print('   Уберите кавычки из .env файла')
if s.password.startswith('"') and s.password.endswith('"'):
    print('\n⚠️  ВНИМАНИЕ: Password содержит кавычки!')
    print('   Уберите кавычки из .env файла')

