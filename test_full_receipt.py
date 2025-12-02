#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Полный тест: распознавание QR-кода и получение всех позиций чека."""

import sys
import os
import json
from pathlib import Path

# Настройка путей
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
os.environ.setdefault("ENCRYPTION_SECRET", "dummy_secret")

from services.ocr_worker.qr_scanner import detect_qr_code, QRCodeNotFoundError
from services.ocr_worker.receipt_scraper import scrape_receipt_data, ScrapingError


def print_section(title: str, char: str = "="):
    """Печатает заголовок секции."""
    print("\n" + char * 80)
    print(f"  {title}")
    print(char * 80)


def main():
    image_file = project_root / "5292124673841762126.jpg"
    
    print_section("🔍 ПОЛНЫЙ ТЕСТ: QR-КОД И ПОЛУЧЕНИЕ ПОЗИЦИЙ ЧЕКА", "=")
    print(f"📄 Файл: {image_file}")
    
    # Шаг 1: Распознавание QR-кода
    print_section("Шаг 1: Распознавание QR-кода")
    try:
        with open(image_file, "rb") as f:
            image_bytes = f.read()
        print(f"✅ Изображение загружено: {len(image_bytes):,} байт")
        
        print("⏳ Распознавание QR-кода с помощью QReader...")
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
    
    # Шаг 2: Получение данных чека
    print_section("Шаг 2: Получение данных чека со страницы")
    try:
        print(f"⏳ Переход по URL и парсинг страницы...")
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
    
    # Шаг 3: Вывод результатов
    print_section("Шаг 3: РЕЗУЛЬТАТЫ ОБРАБОТКИ", "=")
    
    print("\n📋 ОСНОВНАЯ ИНФОРМАЦИЯ:")
    print(f"  - Торговец: {scraped_data.get('merchant', 'не определен')}")
    print(f"  - Дата покупки: {scraped_data.get('purchase_ts', 'не определена')}")
    total = scraped_data.get('total')
    if total:
        print(f"  - Общая сумма: {total / 100:.2f} грн ({total} копеек)")
    else:
        print(f"  - Общая сумма: не определена")
    
    line_items = scraped_data.get('line_items', [])
    print(f"\n📦 ПОЗИЦИИ ЧЕКА ({len(line_items)}):")
    
    if not line_items:
        print("  ⚠️  Позиции не найдены")
    else:
        for i, item in enumerate(line_items, 1):
            price = item.get('price', 0)
            price_uah = price / 100 if price else 0
            quantity = item.get('quantity', 1)
            name = item.get('name', 'неизвестно')
            
            print(f"\n  {i}. {name}")
            print(f"     Количество: {quantity} шт.")
            print(f"     Цена за единицу: {price_uah:.2f} грн ({price} копеек)")
            if quantity > 1:
                total_item = price * quantity
                print(f"     Итого за позицию: {total_item / 100:.2f} грн ({total_item} копеек)")
    
    print("\n📊 СТАТИСТИКА:")
    confidence_data = scraped_data.get('confidence', {})
    print(f"  - Средняя уверенность: {confidence_data.get('mean', 1.0):.2%}")
    print(f"  - Количество позиций: {confidence_data.get('token_count', len(line_items))}")
    
    # Сохранение результата в JSON
    output_file = project_root / "receipt_data.json"
    try:
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

