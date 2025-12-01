#!/usr/bin/env python3
"""Минимальный тест OCR без зависимостей от проекта."""

import cv2
import numpy as np
from PIL import Image
import pytesseract

# Настройка пути к Tesseract
pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'

def main():
    check_file = "check.jpg"
    
    print(f"📄 Обработка файла: {check_file}")
    print("=" * 60)
    
    # Читаем и обрабатываем изображение
    image = cv2.imread(check_file)
    if image is None:
        print("❌ Не удалось загрузить изображение")
        return 1
    
    print(f"✓ Размер изображения: {image.shape[1]}x{image.shape[0]}")
    
    # Предобработка
    print("\n🔧 Предобработка...")
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    equalized = clahe.apply(grayscale)
    denoised = cv2.bilateralFilter(equalized, d=9, sigmaColor=75, sigmaSpace=75)
    thresholded = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 3
    )
    
    # Распознавание
    print("🔍 Распознавание...")
    pil_image = Image.fromarray(thresholded)
    
    config = "--oem 1 --psm 4"
    text = pytesseract.image_to_string(pil_image, lang="ukr+rus+eng", config=config)
    
    print("\n" + "=" * 60)
    print("📝 РАСПОЗНАННЫЙ ТЕКСТ:")
    print("=" * 60)
    print(text)
    print("=" * 60)
    
    # Проверка на "Дарниця"
    print("\n🔎 ПРОВЕРКА 'Дарниця':")
    search_terms = ["Дарниця", "Дарница", "Дарницю", "Дарниці"]
    found = [t for t in search_terms if t in text]
    
    if found:
        print(f"✅ Найдено: {', '.join(found)}")
        for term in found:
            idx = text.find(term)
            context = text[max(0, idx-30):min(len(text), idx+len(term)+30)]
            print(f"   Контекст: ...{context}...")
    else:
        print("❌ Не найдено")
    
    # Статистика уверенности
    print("\n📊 СТАТИСТИКА:")
    data = pytesseract.image_to_data(pil_image, lang="ukr+rus+eng", config=config, output_type=pytesseract.Output.DICT)
    confs = [float(c) for c in data['conf'] if c != '-1' and c != '']
    if confs:
        print(f"   Средняя уверенность: {sum(confs)/len(confs):.1f}%")
        print(f"   Минимум: {min(confs):.1f}%")
        print(f"   Максимум: {max(confs):.1f}%")
        print(f"   Всего слов: {len(confs)}")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

