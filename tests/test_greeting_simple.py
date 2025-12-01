"""Упрощенный тест приветствия без conftest."""
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Устанавливаем переменные окружения
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("ENCRYPTION_SECRET", "test-encryption-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, ReplyKeyboardMarkup, User

from apps.telegram_bot.handlers.commands import cmd_start


@pytest.mark.asyncio
async def test_start_command_greets_and_requests_phone():
    """Тест: команда /start здоровается и запрашивает номер телефона."""
    # Создаем мок клиента
    mock_receipt_client = AsyncMock()
    mock_receipt_client.register_user.return_value = {"has_phone": False}
    
    # Создаем мок пользователя
    mock_user = MagicMock(spec=User)
    mock_user.id = 12345
    mock_user.first_name = "Test"
    mock_user.language_code = "uk"
    
    # Создаем мок сообщения
    mock_message = MagicMock(spec=Message)
    mock_message.from_user = mock_user
    mock_message.contact = None
    mock_message.answer = AsyncMock()
    
    # Вызываем обработчик команды /start
    await cmd_start(mock_message, mock_receipt_client)
    
    # Проверяем, что был вызван register_user
    mock_receipt_client.register_user.assert_called_once_with(
        telegram_id=12345,
        phone_number=None,
        locale="uk",
    )
    
    # Проверяем, что было отправлено сообщение
    assert mock_message.answer.called, "Бот должен отправить сообщение"
    
    # Получаем аргументы вызова answer
    call_args = mock_message.answer.call_args
    sent_text = call_args[0][0]  # Первый позиционный аргумент - текст сообщения
    sent_kwargs = call_args[1]  # Ключевые аргументы
    
    print(f"\n📝 Текст сообщения:\n{sent_text}\n")
    
    # Проверяем, что в тексте есть приветствие
    assert "Hello" in sent_text or "Привет" in sent_text or "Вітаю" in sent_text or "Привіт" in sent_text, \
        f"Сообщение должно содержать приветствие, получено: {sent_text}"
    
    # Проверяем, что в тексте есть запрос номера телефона
    assert "phone" in sent_text.lower() or "номер" in sent_text.lower() or "телефон" in sent_text.lower() or "телефону" in sent_text.lower(), \
        f"Сообщение должно запрашивать номер телефона, получено: {sent_text}"
    
    # Проверяем, что была отправлена клавиатура с кнопкой запроса контакта
    assert "reply_markup" in sent_kwargs, "Должна быть отправлена клавиатура"
    reply_markup = sent_kwargs["reply_markup"]
    assert isinstance(reply_markup, ReplyKeyboardMarkup), \
        f"Клавиатура должна быть ReplyKeyboardMarkup, получено: {type(reply_markup)}"
    
    # Проверяем, что в клавиатуре есть кнопка с request_contact=True
    keyboard = reply_markup.keyboard
    assert len(keyboard) > 0, "Клавиатура должна содержать кнопки"
    button = keyboard[0][0]
    assert button.request_contact is True, "Кнопка должна запрашивать контакт"
    
    print("✅ Все проверки пройдены успешно!")

