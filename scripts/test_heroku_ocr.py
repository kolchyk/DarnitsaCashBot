#!/usr/bin/env python3
"""Тест механизма OCR на Heroku с использованием локального файла check.jpg.

Этот скрипт имитирует процесс обработки чека, который происходит на Heroku:
1. Загрузка изображения (вместо storage - локальный файл)
2. Предобработка изображения
3. Распознавание текста с помощью Tesseract
4. Постобработка и структурирование данных
5. Вывод результатов

Использование:
    python scripts/test_heroku_ocr.py
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.ocr_worker.preprocess import preprocess_image, UnreadableImageError
from services.ocr_worker.tesseract_runner import TesseractRunner, TesseractRuntimeError
from services.ocr_worker.postprocess import build_structured_payload
from libs.common.config import AppSettings
from libs.data.repositories import CatalogRepository
from libs.data import async_session_factory


def print_section(title: str, char: str = "="):
    """Печатает заголовок секции."""
    print("\n" + char * 80)
    print(f"  {title}")
    print(char * 80)


def print_dict(data: dict, indent: int = 0):
    """Печатает словарь в читаемом формате."""
    for key, value in data.items():
        if isinstance(value, dict):
            print(" " * indent + f"{key}:")
            print_dict(value, indent + 2)
        elif isinstance(value, list):
            print(" " * indent + f"{key}: [{len(value)} items]")
            if value and isinstance(value[0], dict):
                for i, item in enumerate(value[:3]):  # Показываем первые 3 элемента
                    print(" " * (indent + 2) + f"[{i}]:")
                    print_dict(item, indent + 4)
                if len(value) > 3:
                    print(" " * (indent + 2) + f"... и еще {len(value) - 3} элементов")
        else:
            print(" " * indent + f"{key}: {value}")


async def main():
    """Основная функция тестирования OCR."""
    # Инициализация настроек
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
    os.environ.setdefault("ENCRYPTION_SECRET", "dummy_secret")
    
    settings = AppSettings()
    
    # Путь к файлу чека
    check_file = project_root / "check.jpg"
    
    if not check_file.exists():
        print(f"❌ Файл {check_file} не найден!")
        return 1
    
    print_section("🔍 ТЕСТИРОВАНИЕ МЕХАНИЗМА OCR НА HEROKU", "=")
    print(f"📄 Файл: {check_file}")
    print(f"📅 Время: {datetime.now().isoformat()}")
    
    # Шаг 1: Чтение изображения
    print_section("Шаг 1: Загрузка изображения")
    try:
        with open(check_file, "rb") as f:
            image_bytes = f.read()
        print(f"✅ Размер файла: {len(image_bytes):,} байт ({len(image_bytes) / 1024:.2f} KB)")
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return 1
    
    # Шаг 2: Предобработка изображения
    print_section("Шаг 2: Предобработка изображения")
    try:
        preprocess_result = preprocess_image(image_bytes, save_intermediates=False)
        print("✅ Предобработка завершена успешно")
        print("\n📊 Метаданные предобработки:")
        print_dict(preprocess_result.metadata, indent=2)
    except UnreadableImageError as e:
        print(f"❌ Ошибка: Изображение нечитаемо - {e}")
        return 1
    except Exception as e:
        print(f"❌ Ошибка предобработки: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Шаг 3: Распознавание текста с помощью Tesseract
    print_section("Шаг 3: Распознавание текста (Tesseract OCR)")
    try:
        # Используем только украинский язык для распознавания
        settings.ocr_languages = "ukr"
        runner = TesseractRunner(settings)
        print(f"✅ Tesseract инициализирован")
        print(f"   - Языки: {settings.ocr_languages} (только украинский)")
        print(f"   - TESSDATA_PREFIX: {os.environ.get('TESSDATA_PREFIX', 'не установлен')}")
        
        tesseract_result = runner.run(preprocess_result)
        print("✅ Распознавание завершено успешно")
        
        print("\n📊 Статистика по профилям:")
        for profile_name, tokens in tesseract_result.tokens_by_profile.items():
            stats = tesseract_result.stats.get(profile_name, {})
            print(f"\n  Профиль '{profile_name}':")
            print(f"    - Токенов: {stats.get('token_count', 0)}")
            print(f"    - Средняя уверенность: {stats.get('mean_confidence', 0):.2%}")
            
            # Показываем первые несколько токенов
            if tokens:
                sample_text = " ".join(token.text for token in tokens[:10])
                print(f"    - Пример текста: {sample_text[:100]}...")
    except TesseractRuntimeError as e:
        print(f"❌ Ошибка Tesseract: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"❌ Ошибка распознавания: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Шаг 4: Постобработка и структурирование данных
    print_section("Шаг 4: Постобработка и структурирование данных")
    # Сохраняем оригинальные кластеры для поиска кириллицы (до нормализации)
    from services.ocr_worker.postprocess import cluster_tokens_by_line
    line_clusters_original = cluster_tokens_by_line(tesseract_result.tokens_by_profile.get("line_items", []))
    
    try:
        # Загружаем каталог из БД (если доступна)
        catalog_aliases = {}
        try:
            async with async_session_factory() as session:
                catalog_repo = CatalogRepository(session)
                catalog = await catalog_repo.list_active()
                catalog_aliases = {
                    item.sku_code: [alias.lower() for alias in item.product_aliases] 
                    for item in catalog
                }
                print(f"✅ Загружен каталог: {len(catalog_aliases)} SKU")
        except Exception as e:
            print(f"⚠️  Не удалось загрузить каталог из БД: {e}")
            print("   Продолжаем без каталога...")
        
        structured_payload = build_structured_payload(
            preprocess_metadata=preprocess_result.metadata,
            tesseract_stats=tesseract_result.stats,
            tokens_by_profile=tesseract_result.tokens_by_profile,
            catalog_aliases=catalog_aliases,
            settings=settings,
        )
        print("✅ Структурирование данных завершено")
    except Exception as e:
        print(f"❌ Ошибка постобработки: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Шаг 5: Вывод результатов
    print_section("Шаг 5: РЕЗУЛЬТАТЫ ОБРАБОТКИ", "=")
    
    print("\n📋 ОСНОВНАЯ ИНФОРМАЦИЯ:")
    print(f"  - Торговец: {structured_payload.get('merchant', 'не определен')}")
    print(f"  - Дата покупки: {structured_payload.get('purchase_ts', 'не определена')}")
    print(f"  - Общая сумма: {structured_payload.get('total', 0) / 100 if structured_payload.get('total') else 0:.2f} грн")
    
    print(f"\n📦 ТОВАРЫ ({len(structured_payload.get('line_items', []))}):")
    line_items = structured_payload.get('line_items', [])
    # Создаем маппинг оригинальных текстов к нормализованным
    original_texts = {}
    if 'line_clusters_original' in locals():
        for i, cluster in enumerate(line_clusters_original):
            if i < len(line_items):
                original_texts[i] = cluster.text
    
    for i, item in enumerate(line_items, 1):
        price_uah = item.get('price', 0) / 100 if item.get('price') else 0
        quantity = item.get('quantity', 1)
        confidence = item.get('confidence', 0)
        sku_code = item.get('sku_code')
        sku_score = item.get('sku_match_score', 0)
        
        normalized_name = item.get('name', 'неизвестно')
        original_name = original_texts.get(i-1, normalized_name)
        
        print(f"\n  {i}. {normalized_name}")
        if original_name != normalized_name and any(ord(c) > 127 for c in original_name):
            print(f"     (оригинал: {original_name})")
        print(f"     Количество: {quantity}")
        print(f"     Цена: {price_uah:.2f} грн")
        print(f"     Уверенность: {confidence:.2%}")
        if sku_code:
            print(f"     SKU: {sku_code} (совпадение: {sku_score:.2%})")
    
    print("\n📊 СТАТИСТИКА УВЕРЕННОСТИ:")
    confidence_data = structured_payload.get('confidence', {})
    print(f"  - Средняя уверенность: {confidence_data.get('mean', 0):.2%}")
    print(f"  - Минимальная: {confidence_data.get('min', 0):.2%}")
    print(f"  - Максимальная: {confidence_data.get('max', 0):.2%}")
    print(f"  - Количество токенов: {confidence_data.get('token_count', 0)}")
    print(f"  - Кандидат на авто-принятие: {confidence_data.get('auto_accept_candidate', False)}")
    
    print("\n⚠️  АНОМАЛИИ:")
    anomalies = structured_payload.get('anomalies', [])
    if anomalies:
        for anomaly in anomalies:
            print(f"  - {anomaly}")
    else:
        print("  ✅ Аномалий не обнаружено")
    
    print(f"\n🔍 ТРЕБУЕТСЯ РУЧНАЯ ПРОВЕРКА: {structured_payload.get('manual_review_required', False)}")
    
    # Проверка наличия слова "Дарниця"
    print_section("ПРОВЕРКА НАЛИЧИЯ ПРЕПАРАТОВ 'Дарниця'")
    # Учитываем различные варианты написания и транслитерацию через unidecode
    search_terms_cyrillic = ["дарниця", "дарница", "дарниці", "дарницю", "дарницею"]
    search_terms_latin = ["darnitsa", "darnitsia", "kaptopres-darnitsia", "kaptopres-darnitsa"]
    
    found_items = []
    # Проверяем оригинальные тексты (до нормализации) для поиска кириллицы
    if 'line_clusters_original' in locals():
        for i, cluster in enumerate(line_clusters_original):
            original_text_lower = cluster.text.lower()
            # Ищем кириллические варианты в оригинальном тексте
            if any(term in original_text_lower for term in search_terms_cyrillic):
                if i < len(line_items):
                    found_items.append((i, line_items[i], cluster.text))
    
    # Также проверяем нормализованные имена товаров (для транслитерации)
    for i, item in enumerate(line_items):
        name_lower = item.get('name', '').lower()
        if any(term in name_lower for term in search_terms_latin):
            # Проверяем, не добавлен ли уже этот товар
            if not any(idx == i for idx, _, _ in found_items):
                original_text = original_texts.get(i, item.get('name', ''))
                found_items.append((i, item, original_text))
    
    if found_items:
        print(f"✅ Найдено {len(found_items)} препаратов 'Дарниця':")
        for idx, item, original_text in found_items:
            price_uah = item.get('price', 0) / 100 if item.get('price') else 0
            normalized_name = item.get('name', 'неизвестно')
            print(f"  {idx+1}. {normalized_name}")
            if original_text != normalized_name:
                print(f"      (оригинал: {original_text})")
            print(f"      Цена: {price_uah:.2f} грн")
    else:
        print("❌ Препараты 'Дарниця' не найдены")
        print("   Проверенные варианты:")
        print(f"   - Кириллица: {', '.join(search_terms_cyrillic)}")
        print(f"   - Транслитерация: {', '.join(search_terms_latin)}")
    
    # Сохранение полного результата в JSON
    output_file = project_root / "scripts" / "ocr_result.json"
    try:
        # Конвертируем datetime в строку для JSON
        payload_for_json = json.loads(json.dumps(structured_payload, default=str))
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(payload_for_json, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Полный результат сохранен в: {output_file}")
    except Exception as e:
        print(f"\n⚠️  Не удалось сохранить результат в JSON: {e}")
    
    print_section("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО", "=")
    
    return 0


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))

