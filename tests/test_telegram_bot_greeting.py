"""Тесты для проверки приветствия и запроса номера телефона в Telegram боте."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Contact, Message, ReplyKeyboardMarkup, User

from apps.telegram_bot.handlers.commands import cmd_start, handle_contact


@pytest.fixture
def mock_receipt_client():
    """Мок клиента для работы с API."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_user():
    """Создает мок пользователя Telegram."""
    user = MagicMock(spec=User)
    user.id = 12345
    user.first_name = "Test"
    user.language_code = "uk"
    return user


@pytest.fixture
def mock_message(mock_user):
    """Создает мок сообщения Telegram."""
    message = MagicMock(spec=Message)
    message.from_user = mock_user
    message.contact = None
    message.answer = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_start_command_greets_and_requests_phone(mock_message, mock_receipt_client):
    """Тест: команда /start здоровается и запрашивает номер телефона."""
    # Настраиваем мок клиента: пользователь без номера телефона
    mock_receipt_client.register_user.return_value = {"has_phone": False}
    
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
    
    # Проверяем, что в тексте есть приветствие
    assert "Hello" in sent_text or "Привет" in sent_text or "Вітаю" in sent_text, \
        f"Сообщение должно содержать приветствие, получено: {sent_text}"
    
    # Проверяем, что в тексте есть запрос номера телефона
    assert "phone" in sent_text.lower() or "номер" in sent_text.lower() or "телефон" in sent_text.lower(), \
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


@pytest.mark.asyncio
async def test_start_command_greets_existing_user_with_phone(mock_message, mock_receipt_client):
    """Тест: команда /start здоровается с пользователем, у которого уже есть номер."""
    # Настраиваем мок клиента: пользователь с номером телефона
    mock_receipt_client.register_user.return_value = {"has_phone": True}
    
    # Вызываем обработчик команды /start
    await cmd_start(mock_message, mock_receipt_client)
    
    # Проверяем, что был вызван register_user
    mock_receipt_client.register_user.assert_called_once()
    
    # Проверяем, что было отправлено сообщение
    assert mock_message.answer.called, "Бот должен отправить сообщение"
    
    # Получаем аргументы вызова answer
    call_args = mock_message.answer.call_args
    sent_text = call_args[0][0]
    sent_kwargs = call_args[1]
    
    # Проверяем, что в тексте есть приветствие
    assert "Hello" in sent_text or "Привет" in sent_text or "Вітаю" in sent_text, \
        f"Сообщение должно содержать приветствие, получено: {sent_text}"
    
    # Проверяем, что клавиатура была удалена (ReplyKeyboardRemove)
    from aiogram.types import ReplyKeyboardRemove
    assert isinstance(sent_kwargs.get("reply_markup"), ReplyKeyboardRemove), \
        "Клавиатура должна быть удалена для пользователя с номером"


@pytest.mark.asyncio
async def test_start_command_with_user_name(mock_message, mock_receipt_client):
    """Тест: команда /start использует имя пользователя в приветствии."""
    mock_receipt_client.register_user.return_value = {"has_phone": False}
    
    await cmd_start(mock_message, mock_receipt_client)
    
    call_args = mock_message.answer.call_args
    sent_text = call_args[0][0]
    
    # Проверяем, что имя пользователя присутствует в сообщении
    assert "Test" in sent_text, \
        f"Сообщение должно содержать имя пользователя 'Test', получено: {sent_text}"


@pytest.mark.asyncio
async def test_handle_contact_saves_phone(mock_message, mock_receipt_client):
    """Тест: обработка контакта сохраняет номер телефона."""
    # Создаем мок контакта
    contact = MagicMock(spec=Contact)
    contact.phone_number = "+380501234567"
    mock_message.contact = contact
    
    # Настраиваем мок клиента: номер успешно сохранен
    mock_receipt_client.register_user.return_value = {"has_phone": True}
    
    # Вызываем обработчик контакта
    await handle_contact(mock_message, mock_receipt_client)
    
    # Проверяем, что был вызван register_user с номером телефона
    mock_receipt_client.register_user.assert_called_once_with(
        telegram_id=12345,
        phone_number="+380501234567",
        locale="uk",
    )
    
    # Проверяем, что было отправлено подтверждение
    assert mock_message.answer.called, "Бот должен отправить подтверждение"
    
    call_args = mock_message.answer.call_args
    sent_text = call_args[0][0]
    
    # Проверяем, что в сообщении есть подтверждение сохранения
    assert "saved" in sent_text.lower() or "збережено" in sent_text.lower() or "сохранен" in sent_text.lower(), \
        f"Сообщение должно подтверждать сохранение номера, получено: {sent_text}"

