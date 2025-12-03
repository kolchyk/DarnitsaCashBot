#!/usr/bin/env python
"""
Тестовый скрипт для парсинга страницы чека с tax.gov.ua
Использование: python scripts/test_parse_page.py [url]
"""
from __future__ import annotations

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Добавляем корень проекта в путь
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def test_parse_page(url: str, save_html: bool = True) -> None:
    """
    Тестирует парсинг страницы чека с tax.gov.ua
    
    NOTE: Функционал скраппинга Playwright был удален.
    Этот скрипт теперь показывает сообщение об ошибке.
    
    Args:
        url: URL страницы чека
        save_html: Сохранять ли HTML для отладки (не используется)
    """
    from apps.api_gateway.services.ocr.receipt_scraper import scrape_receipt_data, ScrapingError
    
    print("=" * 80)
    print("ТЕСТ ПАРСИНГА СТРАНИЦЫ ЧЕКА")
    print("=" * 80)
    print(f"\n🔗 URL: {url}")
    print(f"⏰ Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)
    
    try:
        print("\n🚀 Начинаем парсинг...")
        print("⚠️  ВНИМАНИЕ: Функционал скраппинга Playwright был удален!")
        result = scrape_receipt_data(url)
        
        print("\n" + "=" * 80)
        print("✅ ПАРСИНГ УСПЕШЕН!")
        print("=" * 80)
        
        # Основная информация
        print("\n📋 ОСНОВНАЯ ИНФОРМАЦИЯ:")
        print(f"   Торговец: {result.get('merchant') or 'Не найдено'}")
        print(f"   Дата покупки: {result.get('purchase_ts') or 'Не найдено'}")
        
        total = result.get('total')
        if total:
            total_uah = total / 100
            print(f"   Сумма: {total_uah:.2f} грн ({total} копеек)")
        else:
            print(f"   Сумма: Не найдено")
        
        line_items = result.get('line_items', [])
        print(f"   Количество позиций: {len(line_items)}")
        
        # Детали позиций
        if line_items:
            print("\n📦 ПОЗИЦИИ В ЧЕКЕ:")
            print("-" * 80)
            total_calculated = 0
            for i, item in enumerate(line_items, 1):
                name = item.get('name', 'Без названия')
                quantity = item.get('quantity', 1)
                price = item.get('price', 0)
                price_uah = price / 100
                item_total = price * quantity
                item_total_uah = item_total / 100
                total_calculated += item_total
                
                print(f"\n   {i}. {name}")
                print(f"      Количество: {quantity}")
                print(f"      Цена за единицу: {price_uah:.2f} грн ({price} копеек)")
                print(f"      Сумма позиции: {item_total_uah:.2f} грн ({item_total} копеек)")
                print(f"      Уверенность: {item.get('confidence', 1.0):.2%}")
                
                if item.get('is_darnitsa'):
                    print(f"      ✅ Продукт Darnitsa")
                if item.get('sku_code'):
                    print(f"      SKU: {item.get('sku_code')}")
            
            print("\n" + "-" * 80)
            print(f"   Итого по позициям: {total_calculated / 100:.2f} грн ({total_calculated} копеек)")
        else:
            print("\n⚠️  Позиции не найдены!")
        
        # Статистика уверенности
        confidence = result.get('confidence', {})
        if confidence:
            print("\n📊 СТАТИСТИКА УВЕРЕННОСТИ:")
            print(f"   Средняя уверенность: {confidence.get('mean', 0):.2%}")
            print(f"   Минимальная: {confidence.get('min', 0):.2%}")
            print(f"   Максимальная: {confidence.get('max', 0):.2%}")
            print(f"   Количество токенов: {confidence.get('token_count', 0)}")
            print(f"   Автопринятие: {'Да' if confidence.get('auto_accept_candidate') else 'Нет'}")
        
        # Дополнительная информация
        print("\n🔍 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:")
        print(f"   Требуется ручная проверка: {'Да' if result.get('manual_review_required') else 'Нет'}")
        
        anomalies = result.get('anomalies', [])
        if anomalies:
            print(f"   ⚠️  Аномалии найдены: {len(anomalies)}")
            for anomaly in anomalies:
                print(f"      - {anomaly}")
        else:
            print(f"   Аномалии: Не найдено")
        
        # Сохранение результатов
        output_dir = PROJECT_ROOT / "scripts" / "test_results"
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = output_dir / f"parse_result_{timestamp}.json"
        
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 Полный результат сохранен в: {json_file}")
        
        # Сохранение HTML (если нужно)
        if save_html:
            print("\n💡 Для сохранения HTML отредактируйте receipt_scraper.py")
            print("   и добавьте сохранение html_content в файл")
        
        return result
        
    except ScrapingError as e:
        print("\n" + "=" * 80)
        print("❌ ОШИБКА ПАРСИНГА")
        print("=" * 80)
        print(f"\n{str(e)}")
        return None
        
    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ НЕОЖИДАННАЯ ОШИБКА")
        print("=" * 80)
        print(f"\nТип ошибки: {type(e).__name__}")
        print(f"Сообщение: {str(e)}")
        print("\nПолный traceback:")
        import traceback
        traceback.print_exc()
        return None


def main() -> None:
    """Главная функция."""
    # URL по умолчанию
    default_url = "https://cabinet.tax.gov.ua/cashregs/check?id=UxI07gWmYOQ&date=20251201&time=16:12&fn=4001246197&sm=46.50"
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = default_url
    
    save_html = "--save-html" in sys.argv
    
    result = test_parse_page(url, save_html=save_html)
    
    print("\n" + "=" * 80)
    if result:
        print("✅ Тест завершен успешно")
    else:
        print("❌ Тест завершен с ошибками")
    print("=" * 80)


if __name__ == "__main__":
    main()

