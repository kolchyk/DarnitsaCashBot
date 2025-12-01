#!/usr/bin/env python3
"""Простой скрипт для проверки наличия слова 'Дарниця' в изображении чека."""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("⚠️  pytesseract или PIL не установлены. Установите: pip install pytesseract pillow")
    print("   Также требуется установить Tesseract: brew install tesseract tesseract-lang")


def check_darnitsa_in_image(image_path: Path) -> dict:
    """Проверяет наличие слова 'Дарниця' в изображении."""
    result = {
        "found": False,
        "text": "",
        "matches": [],
        "error": None
    }
    
    if not HAS_OCR:
        result["error"] = "OCR библиотеки не установлены"
        return result
    
    try:
        # Открываем изображение
        image = Image.open(image_path)
        print(f"✓ Изображение загружено: {image.size[0]}x{image.size[1]} пикселей")
        
        # Распознаем текст
        print("🔍 Распознавание текста...")
        try:
            # Пробуем с украинским языком
            text_ukr = pytesseract.image_to_string(image, lang='ukr+rus+eng')
            result["text"] = text_ukr
        except Exception as e:
            # Если не получилось с языками, пробуем без указания языка
            print(f"⚠️  Ошибка с языками: {e}, пробуем без указания языка...")
            result["text"] = pytesseract.image_to_string(image)
        
        print(f"✓ Распознано символов: {len(result['text'])}")
        
        # Ищем слово "Дарниця" в разных вариантах
        search_terms = [
            "Дарниця", "Дарница", "Дарницю", "Дарниці", 
            "дарниця", "ДАРНИЦЯ", "ДАРНИЦА",
            "Darnitsa", "DARNITSA"  # на случай латиницы
        ]
        
        text_lower = result["text"].lower()
        for term in search_terms:
            if term.lower() in text_lower:
                # Находим все вхождения
                idx = 0
                while True:
                    idx = text_lower.find(term.lower(), idx)
                    if idx == -1:
                        break
                    # Извлекаем контекст
                    start = max(0, idx - 50)
                    end = min(len(result["text"]), idx + len(term) + 50)
                    context = result["text"][start:end]
                    result["matches"].append({
                        "term": term,
                        "position": idx,
                        "context": context
                    })
                    idx += len(term)
        
        result["found"] = len(result["matches"]) > 0
        
    except Exception as e:
        result["error"] = str(e)
        import traceback
        traceback.print_exc()
    
    return result


def main():
    check_file = project_root / "check.jpg"
    
    if not check_file.exists():
        print(f"❌ Файл {check_file} не найден!")
        return 1
    
    print(f"📄 Обработка файла: {check_file}")
    print("=" * 60)
    
    result = check_darnitsa_in_image(check_file)
    
    if result["error"]:
        print(f"❌ Ошибка: {result['error']}")
        return 1
    
    print("\n" + "=" * 60)
    print("📝 РАСПОЗНАННЫЙ ТЕКСТ:")
    print("=" * 60)
    if result["text"]:
        print(result["text"])
    else:
        print("(текст не распознан)")
    print("=" * 60)
    
    print("\n🔎 ПРОВЕРКА НАЛИЧИЯ СЛОВА 'Дарниця':")
    print("=" * 60)
    
    if result["found"]:
        print(f"✅ НАЙДЕНО: {len(result['matches'])} упоминаний слова 'Дарниця'")
        print("\nКонтекст найденных упоминаний:")
        for i, match in enumerate(result["matches"], 1):
            print(f"\n{i}. Найдено: '{match['term']}'")
            print(f"   Контекст: ...{match['context']}...")
    else:
        print("❌ Слово 'Дарниця' не найдено в распознанном тексте")
        print("\nВозможные причины:")
        print("  - Препараты 'Дарниця' отсутствуют в чеке")
        print("  - Низкое качество изображения")
        print("  - Ошибка распознавания текста")
        print("  - Tesseract не настроен для украинского языка")
    
    print("\n" + "=" * 60)
    
    return 0 if result["found"] else 1


if __name__ == "__main__":
    sys.exit(main())

