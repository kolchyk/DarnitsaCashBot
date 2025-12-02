#!/usr/bin/env python3
"""Простой тест функции has_darnitsa_prefix на примере из чека."""

import re
import unicodedata
from unidecode import unidecode

# Константы из libs/common/constants.py
DARNITSA_KEYWORDS_CYRILLIC = [
    "дарниця",
    "дарница",
    "дарниці",
    "дарницю",
    "дарницею",
]
DARNITSA_KEYWORDS_LATIN = [
    "darnitsa",
    "darnitsia",
]

# Копия функции из libs/common/darnitsa.py
_WORD_SEPARATOR_PATTERN = re.compile(r"\s+")


def _normalize_source(text: str | None) -> str:
    """Normalize input text for prefix matching."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.strip()
    normalized = _WORD_SEPARATOR_PATTERN.sub(" ", normalized)
    return normalized


def _starts_with_any(text: str, prefixes) -> bool:
    """Check whether text begins with any of the prefixes (handling separators)."""
    if not text:
        return False
    for prefix in prefixes:
        if not prefix:
            continue
        if text.startswith(prefix):
            if len(text) == len(prefix):
                return True
            next_char = text[len(prefix)]
            if not next_char.isalpha():
                return True
    return False


def has_darnitsa_prefix(text: str | None) -> bool:
    """
    Return True when the provided text starts with a Darnitsa keyword.

    Handles Cyrillic + transliterated Latin variants and tolerates separators like
    spaces, dashes, commas right after the prefix.
    """
    normalized = _normalize_source(text).lower()
    transliterated = unidecode(normalized)
    if _starts_with_any(normalized, (kw.lower() for kw in DARNITSA_KEYWORDS_CYRILLIC)):
        return True
    return _starts_with_any(transliterated, (kw.lower() for kw in DARNITSA_KEYWORDS_LATIN))


def test_examples():
    """Тестируем функцию на различных примерах."""
    
    # Примеры из чека
    test_cases = [
        # Ожидаем True (префикс "Дарниця" в начале)
        ("№ 13204 Каптопрес-Дарниця табл. 25 мг №20", True, "Каптопрес-Дарниця"),
        ("Дарниця Цитрамон", True, "Дарниця в начале"),
        ("Дарниця Вітамін С", True, "Дарниця в начале"),
        ("DARNITSA CITRAMON", True, "DARNITSA в начале (латиница)"),
        ("KAPTOPRES-DARNITSIA TABL. 25 MG", True, "DARNITSIA после дефиса"),
        
        # Ожидаем False (нет префикса в начале)
        ("Цитрамон Дарниця", False, "Дарниця в конце"),
        ("Препарат от Дарниця", False, "Дарниця в середине"),
        ("Аптека Дарниця", False, "Дарниця не в начале"),
        ("Каптопрес от Дарниця", False, "Дарниця не в начале"),
        
        # Граничные случаи
        ("", False, "Пустая строка"),
        ("Дарниця", True, "Только Дарниця"),
        ("Дарниця-Цитрамон", True, "Дарниця с дефисом"),
        ("Дарниця, Цитрамон", True, "Дарниця с запятой"),
        ("Дарниця Цитрамон", True, "Дарниця с пробелом"),
    ]
    
    print("=" * 80)
    print("ТЕСТИРОВАНИЕ ФУНКЦИИ has_darnitsa_prefix")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for text, expected, description in test_cases:
        result = has_darnitsa_prefix(text)
        status = "✅" if result == expected else "❌"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"\n{status} Тест: {description}")
        print(f"   Текст: '{text}'")
        print(f"   Ожидалось: {expected}, Получено: {result}")
        
        if result != expected:
            print(f"   ⚠️  ОШИБКА!")
    
    print("\n" + "=" * 80)
    print(f"РЕЗУЛЬТАТЫ: Успешно: {passed}, Ошибок: {failed}")
    print("=" * 80)
    
    # Специальная проверка для примера из чека
    print("\n" + "=" * 80)
    print("ПРОВЕРКА ПРИМЕРА ИЗ ЧЕКА")
    print("=" * 80)
    
    receipt_example = "№ 13204 Каптопрес-Дарниця табл. 25 мг №20"
    result = has_darnitsa_prefix(receipt_example)
    
    print(f"\nТекст из чека: '{receipt_example}'")
    print(f"Результат has_darnitsa_prefix: {result}")
    
    if result:
        print("✅ ПРЕФИКС НАЙДЕН - алгоритм работает корректно!")
    else:
        print("❌ ПРЕФИКС НЕ НАЙДЕН - требуется проверка алгоритма")
    
    # Проверяем также варианты написания
    variants = [
        "Каптопрес-Дарниця",
        "KAPTOPRES-DARNITSIA",
        "Каптопрес Дарниця",
        "KAPTOPRES DARNITSIA",
    ]
    
    print("\nПроверка вариантов написания:")
    for variant in variants:
        res = has_darnitsa_prefix(variant)
        print(f"  '{variant}' -> {res}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(test_examples())

