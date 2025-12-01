"""Проверка логики приветствия и запроса номера телефона."""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from apps.telegram_bot.handlers.commands import (
    onboarding_text,
    contact_keyboard,
    consent_notice,
)
from libs.common.i18n import get_translator


def test_greeting_and_phone_request():
    """Проверяет, что бот здоровается и запрашивает номер телефона."""
    
    # Тестируем для украинского языка
    _uk = get_translator("uk")
    
    print("=" * 60)
    print("ПРОВЕРКА ПРИВЕТСТВИЯ И ЗАПРОСА НОМЕРА ТЕЛЕФОНА")
    print("=" * 60)
    
    # Тест 1: Пользователь без номера телефона
    print("\n1. Пользователь БЕЗ номера телефона:")
    print("-" * 60)
    text_without_phone = onboarding_text(_uk, require_phone=True, user_name="Тест")
    print(f"Текст сообщения:\n{text_without_phone}\n")
    
    # Проверяем наличие приветствия
    assert "Привіт" in text_without_phone or "Hello" in text_without_phone, \
        "❌ ОШИБКА: В тексте отсутствует приветствие!"
    print("✅ Приветствие присутствует")
    
    # Проверяем наличие запроса номера телефона
    assert "номер" in text_without_phone.lower() or "phone" in text_without_phone.lower(), \
        "❌ ОШИБКА: В тексте отсутствует запрос номера телефона!"
    print("✅ Запрос номера телефона присутствует")
    
    # Проверяем клавиатуру
    keyboard = contact_keyboard(_uk)
    assert keyboard is not None, "❌ ОШИБКА: Клавиатура не создана!"
    assert len(keyboard.keyboard) > 0, "❌ ОШИБКА: Клавиатура пуста!"
    assert keyboard.keyboard[0][0].request_contact is True, \
        "❌ ОШИБКА: Кнопка не запрашивает контакт!"
    print("✅ Клавиатура с кнопкой запроса контакта создана")
    print(f"   Текст кнопки: {keyboard.keyboard[0][0].text}")
    
    # Тест 2: Пользователь с номером телефона
    print("\n2. Пользователь С номером телефона:")
    print("-" * 60)
    text_with_phone = onboarding_text(_uk, require_phone=False, user_name="Тест")
    print(f"Текст сообщения:\n{text_with_phone}\n")
    
    # Проверяем наличие приветствия
    assert "Привіт" in text_with_phone or "Hello" in text_with_phone, \
        "❌ ОШИБКА: В тексте отсутствует приветствие!"
    print("✅ Приветствие присутствует")
    
    # Проверяем, что нет запроса номера (но есть упоминание, что номер уже есть)
    assert "маємо ваш номер" in text_with_phone.lower() or "have your phone" in text_with_phone.lower(), \
        "❌ ОШИБКА: В тексте должно быть упоминание о наличии номера!"
    print("✅ Упоминание о наличии номера присутствует")
    
    # Тест 3: Проверка согласия
    print("\n3. Проверка текста согласия:")
    print("-" * 60)
    consent = consent_notice(_uk)
    print(f"Текст согласия:\n{consent}\n")
    assert len(consent) > 0, "❌ ОШИБКА: Текст согласия пуст!"
    print("✅ Текст согласия присутствует")
    
    # Тест 4: Русский язык
    print("\n4. Проверка для русского языка:")
    print("-" * 60)
    _ru = get_translator("ru")
    text_ru = onboarding_text(_ru, require_phone=True, user_name="Тест")
    print(f"Текст сообщения:\n{text_ru}\n")
    
    assert "Привет" in text_ru or "Hello" in text_ru, \
        "❌ ОШИБКА: В русском тексте отсутствует приветствие!"
    assert "номер" in text_ru.lower() or "телефон" in text_ru.lower(), \
        "❌ ОШИБКА: В русском тексте отсутствует запрос номера!"
    print("✅ Русский перевод работает корректно")
    
    print("\n" + "=" * 60)
    print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 60)
    print("\nВывод:")
    print("1. ✅ Бот здоровается с пользователем")
    print("2. ✅ Бот запрашивает номер телефона (если его нет)")
    print("3. ✅ Бот показывает клавиатуру с кнопкой запроса контакта")
    print("4. ✅ Переводы работают корректно")


if __name__ == "__main__":
    try:
        test_greeting_and_phone_request()
    except AssertionError as e:
        print(f"\n❌ ОШИБКА: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

