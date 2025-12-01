#!/usr/bin/env python3
"""Простой тест OCR без зависимостей от БД и настроек."""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import cv2
import numpy as np
from PIL import Image
import pytesseract

# Настройка пути к Tesseract (для macOS)
pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'

def main():
    check_file = project_root / "check.jpg"
    
    if not check_file.exists():
        print(f"❌ Файл {check_file} не найден!")
        return 1
    
    print(f"📄 Обработка файла: {check_file}")
    print("=" * 60)
    
    # Читаем изображение
    with open(check_file, "rb") as f:
        image_bytes = f.read()
    
    print(f"✓ Размер файла: {len(image_bytes)} байт")
    
    # Декодируем изображение
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    
    if image is None:
        print("❌ Не удалось декодировать изображение")
        return 1
    
    print(f"✓ Размер изображения: {image.shape[1]}x{image.shape[0]}")
    
    # Простая предобработка
    print("\n🔧 Предобработка изображения...")
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Контрастное улучшение
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    equalized = clahe.apply(grayscale)
    
    # Удаление шума
    denoised = cv2.bilateralFilter(equalized, d=9, sigmaColor=75, sigmaSpace=75)
    
    # Адаптивная пороговая обработка
    thresholded = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        41,
        3,
    )
    
    print("✓ Предобработка завершена")
    
    # Распознавание текста
    print("\n🔍 Распознавание текста с помощью Tesseract...")
    
    # Конвертируем в PIL Image
    pil_image = Image.fromarray(thresholded)
    
    # Распознавание с украинским языком
    try:
        config = "--oem 1 --psm 4"
        text = pytesseract.image_to_string(pil_image, lang="ukr+rus+eng", config=config)
        
        print("✓ Распознавание завершено")
        print("\n" + "=" * 60)
        print("📝 РАСПОЗНАННЫЙ ТЕКСТ:")
        print("=" * 60)
        print(text)
        print("=" * 60)
        
        # Проверка наличия слова "Дарниця"
        print("\n🔎 ПРОВЕРКА НАЛИЧИЯ СЛОВА 'Дарниця':")
        print("=" * 60)
        
        search_terms = ["Дарниця", "Дарница", "Дарницю", "Дарниці", "дарниця", "ДАРНИЦЯ"]
        found_terms = []
        
        for term in search_terms:
            if term in text:
                found_terms.append(term)
                idx = text.find(term)
                start = max(0, idx - 50)
                end = min(len(text), idx + len(term) + 50)
                context = text[start:end]
                print(f"\n✓ Найдено слово: '{term}'")
                print(f"  Контекст: ...{context}...")
        
        if found_terms:
            print(f"\n✅ РЕЗУЛЬТАТ: Найдено {len(found_terms)} упоминаний слова 'Дарниця'")
        else:
            print("\n❌ РЕЗУЛЬТАТ: Слово 'Дарниця' не найдено в распознанном тексте")
        
        # Дополнительно: получаем данные с уверенностью
        print("\n📊 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ:")
        print("-" * 60)
        data = pytesseract.image_to_data(pil_image, lang="ukr+rus+eng", config=config, output_type=pytesseract.Output.DICT)
        
        confidences = [float(conf) for conf in data['conf'] if conf != '-1' and conf != '']
        if confidences:
            print(f"Средняя уверенность: {sum(confidences) / len(confidences):.2f}%")
            print(f"Минимальная уверенность: {min(confidences):.2f}%")
            print(f"Максимальная уверенность: {max(confidences):.2f}%")
            print(f"Всего слов: {len(confidences)}")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"❌ Ошибка распознавания: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

