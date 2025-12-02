#!/usr/bin/env python3
"""Тест распознавания QR-кода и получения товаров со страницы по фото чека.

Этот скрипт тестирует процесс обработки чека через QR-код:
1. Загрузка изображения чека
2. Распознавание QR-кода на изображении
3. Получение данных о товарах со страницы по URL из QR-кода

Использование:
    python scripts/test_qr_scraping.py [путь_к_файлу.jpg]
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from services.ocr_worker.qr_scanner import detect_qr_code, QRCodeNotFoundError
    from services.ocr_worker.receipt_scraper import scrape_receipt_data, ScrapingError
    from libs.common.config import AppSettings
    from libs.common.logging import configure_logging
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("\n✅ Используются только стандартные библиотеки:")
    print("   - OpenCV (для QR-кода) - уже установлен")
    print("   - httpx (для HTTP запросов) - уже установлен")
    print("   - html.parser (стандартная библиотека Python)")
    print("\n📦 Если OpenCV не установлен:")
    print("   pip install opencv-python-headless")
    sys.exit(1)


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
                for i, item in enumerate(value[:5]):  # Показываем первые 5 элементов
                    print(" " * (indent + 2) + f"[{i}]:")
                    print_dict(item, indent + 4)
                if len(value) > 5:
                    print(" " * (indent + 2) + f"... и еще {len(value) - 5} элементов")
        else:
            print(" " * indent + f"{key}: {value}")


def main():
    """Основная функция тестирования QR-кода и скрапинга."""
    # Инициализация настроек
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
    os.environ.setdefault("ENCRYPTION_SECRET", "dummy_secret")
    
    configure_logging()
    
    # Определяем путь к файлу
    if len(sys.argv) > 1:
        image_file = Path(sys.argv[1])
    else:
        # По умолчанию используем файл из корня проекта
        image_file = project_root / "5292124673841762126.jpg"
    
    if not image_file.exists():
        print(f"❌ Файл {image_file} не найден!")
        print("\nИспользование:")
        print(f"  python {sys.argv[0]} [путь_к_файлу.jpg]")
        return 1
    
    print_section("🔍 ТЕСТИРОВАНИЕ РАСПОЗНАВАНИЯ QR-КОДА И ПОЛУЧЕНИЯ ТОВАРОВ", "=")
    print(f"📄 Файл: {image_file}")
    print(f"📅 Время: {datetime.now().isoformat()}")
    
    # Шаг 1: Чтение изображения
    print_section("Шаг 1: Загрузка изображения")
    try:
        with open(image_file, "rb") as f:
            image_bytes = f.read()
        print(f"✅ Размер файла: {len(image_bytes):,} байт ({len(image_bytes) / 1024:.2f} KB)")
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Шаг 2: Распознавание QR-кода
    print_section("Шаг 2: Распознавание QR-кода")
    try:
        qr_url = detect_qr_code(image_bytes)
        
        if not qr_url:
            print("❌ QR-код не найден в изображении")
            return 1
        
        print(f"✅ QR-код успешно распознан!")
        print(f"   URL: {qr_url}")
    except QRCodeNotFoundError as e:
        print(f"❌ Ошибка: QR-код не найден - {e}")
        return 1
    except Exception as e:
        print(f"❌ Ошибка распознавания QR-кода: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Шаг 3: Получение данных со страницы
    print_section("Шаг 3: Получение данных о товарах со страницы")
    try:
        scraped_data = scrape_receipt_data(qr_url)
        print("✅ Данные успешно получены со страницы")
    except ScrapingError as e:
        print(f"❌ Ошибка получения данных со страницы: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"❌ Неожиданная ошибка при получении данных: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Шаг 4: Вывод результатов
    print_section("Шаг 4: РЕЗУЛЬТАТЫ ОБРАБОТКИ", "=")
    
    print("\n📋 ОСНОВНАЯ ИНФОРМАЦИЯ:")
    print(f"  - Торговец: {scraped_data.get('merchant', 'не определен')}")
    print(f"  - Дата покупки: {scraped_data.get('purchase_ts', 'не определена')}")
    total = scraped_data.get('total')
    if total:
        print(f"  - Общая сумма: {total / 100:.2f} грн ({total} копеек)")
    else:
        print(f"  - Общая сумма: не определена")
    
    line_items = scraped_data.get('line_items', [])
    print(f"\n📦 ТОВАРЫ ({len(line_items)}):")
    
    if not line_items:
        print("  ⚠️  Товары не найдены")
    else:
        for i, item in enumerate(line_items, 1):
            price = item.get('price', 0)
            price_uah = price / 100 if price else 0
            quantity = item.get('quantity', 1)
            confidence = item.get('confidence', 1.0)
            sku_code = item.get('sku_code')
            sku_score = item.get('sku_match_score', 0)
            is_darnitsa = item.get('is_darnitsa', False)
            
            name = item.get('name', 'неизвестно')
            original_name = item.get('original_name', name)
            
            print(f"\n  {i}. {name}")
            if original_name != name:
                print(f"     (оригинал: {original_name})")
            print(f"     Количество: {quantity} шт.")
            print(f"     Цена: {price_uah:.2f} грн ({price} копеек)")
            print(f"     Уверенность: {confidence:.2%}")
            if is_darnitsa:
                print(f"     ✅ Препарат Дарниця: ДА")
            if sku_code:
                print(f"     SKU: {sku_code} (совпадение: {sku_score:.2%})")
    
    print("\n📊 СТАТИСТИКА УВЕРЕННОСТИ:")
    confidence_data = scraped_data.get('confidence', {})
    print(f"  - Средняя уверенность: {confidence_data.get('mean', 1.0):.2%}")
    print(f"  - Минимальная: {confidence_data.get('min', 1.0):.2%}")
    print(f"  - Максимальная: {confidence_data.get('max', 1.0):.2%}")
    print(f"  - Количество токенов: {confidence_data.get('token_count', len(line_items))}")
    print(f"  - Кандидат на авто-принятие: {confidence_data.get('auto_accept_candidate', True)}")
    
    print("\n⚠️  АНОМАЛИИ:")
    anomalies = scraped_data.get('anomalies', [])
    if anomalies:
        for anomaly in anomalies:
            print(f"  - {anomaly}")
    else:
        print("  ✅ Аномалий не обнаружено")
    
    print(f"\n🔍 ТРЕБУЕТСЯ РУЧНАЯ ПРОВЕРКА: {scraped_data.get('manual_review_required', False)}")
    
    # Сохранение полного результата в JSON
    output_file = project_root / "scripts" / "qr_scraping_result.json"
    try:
        # Конвертируем datetime в строку для JSON
        payload_for_json = json.loads(json.dumps(scraped_data, default=str))
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(payload_for_json, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Полный результат сохранен в: {output_file}")
    except Exception as e:
        print(f"\n⚠️  Не удалось сохранить результат в JSON: {e}")
    
    print_section("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО", "=")
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

