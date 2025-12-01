#!/usr/bin/env python3
"""Скрипт для распознавания чека и проверки наличия препаратов со словом 'Дарниця'."""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.ocr_worker.preprocess import preprocess_image
from services.ocr_worker.tesseract_runner import TesseractRunner
from libs.common.config import AppSettings


def main():
    # Инициализация настроек
    # Используем минимальные настройки для работы без БД
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
    os.environ.setdefault("ENCRYPTION_SECRET", "dummy_secret")
    
    settings = AppSettings()
    
    # Путь к файлу чека
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
    
    # Предобработка изображения
    print("\n🔧 Предобработка изображения...")
    try:
        preprocess_result = preprocess_image(image_bytes, save_intermediates=False)
        print(f"✓ Предобработка завершена")
        print(f"  - Размер оригинала: {preprocess_result.metadata['original_shape']}")
        print(f"  - Применённые фильтры: {', '.join(preprocess_result.metadata['filters'])}")
        if 'deskew_angle' in preprocess_result.metadata:
            print(f"  - Угол поворота: {preprocess_result.metadata['deskew_angle']:.2f}°")
    except Exception as e:
        print(f"❌ Ошибка предобработки: {e}")
        return 1
    
    # Распознавание текста с помощью Tesseract
    print("\n🔍 Распознавание текста с помощью Tesseract...")
    try:
        runner = TesseractRunner(settings)
        tesseract_result = runner.run(preprocess_result)
        print(f"✓ Распознавание завершено")
        
        # Собираем весь текст из всех профилей
        all_text = []
        all_tokens = []
        
        for profile_name, tokens in tesseract_result.tokens_by_profile.items():
            profile_text = " ".join(token.text for token in tokens)
            all_text.append(profile_text)
            all_tokens.extend(tokens)
            
            stats = tesseract_result.stats.get(profile_name, {})
            print(f"\n  Профиль '{profile_name}':")
            print(f"    - Токенов: {stats.get('token_count', 0)}")
            print(f"    - Средняя уверенность: {stats.get('mean_confidence', 0):.2%}")
            if profile_text.strip():
                print(f"    - Текст: {profile_text[:100]}...")
        
        full_text = " ".join(all_text)
        
        print("\n" + "=" * 60)
        print("📝 РАСПОЗНАННЫЙ ТЕКСТ:")
        print("=" * 60)
        print(full_text)
        print("=" * 60)
        
        # Проверка наличия слова "Дарниця"
        print("\n🔎 ПРОВЕРКА НАЛИЧИЯ СЛОВА 'Дарниця':")
        print("=" * 60)
        
        # Ищем в разных вариантах написания
        search_terms = ["Дарниця", "Дарница", "Дарницю", "Дарниці", "дарниця", "ДАРНИЦЯ"]
        found_terms = []
        
        for term in search_terms:
            if term in full_text:
                found_terms.append(term)
                # Находим контекст вокруг слова
                idx = full_text.find(term)
                start = max(0, idx - 50)
                end = min(len(full_text), idx + len(term) + 50)
                context = full_text[start:end]
                print(f"\n✓ Найдено слово: '{term}'")
                print(f"  Контекст: ...{context}...")
        
        if found_terms:
            print(f"\n✅ РЕЗУЛЬТАТ: Найдено {len(found_terms)} упоминаний слова 'Дарниця'")
            
            # Ищем препараты в строковых позициях
            print("\n📦 АНАЛИЗ ПРЕПАРАТОВ:")
            print("-" * 60)
            
            # Ищем строки с товарами (line_items)
            line_items_tokens = tesseract_result.tokens_by_profile.get("line_items", [])
            if line_items_tokens:
                # Группируем токены по строкам
                from services.ocr_worker.postprocess import cluster_tokens_by_line
                line_clusters = cluster_tokens_by_line(line_items_tokens)
                
                darnitsa_items = []
                for i, cluster in enumerate(line_clusters, 1):
                    cluster_text = cluster.text
                    for term in search_terms:
                        if term.lower() in cluster_text.lower():
                            darnitsa_items.append((i, cluster_text, cluster.confidence))
                            break
                
                if darnitsa_items:
                    print(f"Найдено {len(darnitsa_items)} строк с препаратами 'Дарниця':")
                    for line_num, text, confidence in darnitsa_items:
                        print(f"  {line_num}. {text} (уверенность: {confidence:.2%})")
                else:
                    print("⚠️  Препараты 'Дарниця' не найдены в строках товаров")
            else:
                print("⚠️  Не удалось извлечь строки товаров")
        else:
            print("\n❌ РЕЗУЛЬТАТ: Слово 'Дарниця' не найдено в распознанном тексте")
            print("   Возможные причины:")
            print("   - Низкое качество изображения")
            print("   - Препараты 'Дарниця' отсутствуют в чеке")
            print("   - Ошибка распознавания текста")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"❌ Ошибка распознавания: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

