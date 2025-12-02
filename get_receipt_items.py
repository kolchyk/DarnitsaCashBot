#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import json
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
os.environ.setdefault("ENCRYPTION_SECRET", "dummy_secret")

from services.ocr_worker.qr_scanner import detect_qr_code
from services.ocr_worker.receipt_scraper import scrape_receipt_data

output_file = project_root / "receipt_result.txt"
json_file = project_root / "receipt_data.json"

with open(output_file, "w", encoding="utf-8") as out:
    out.write("="*80 + "\n")
    out.write("РАСПОЗНАВАНИЕ QR-КОДА И ПОЛУЧЕНИЕ ПОЗИЦИЙ ЧЕКА\n")
    out.write("="*80 + "\n\n")
    
    # Шаг 1: Распознавание QR-кода
    out.write("Шаг 1: Распознавание QR-кода\n")
    out.write("-"*80 + "\n")
    
    image_file = project_root / "5292124673841762126.jpg"
    out.write(f"Файл: {image_file}\n")
    
    with open(image_file, "rb") as f:
        image_bytes = f.read()
    
    out.write(f"Размер изображения: {len(image_bytes):,} байт\n")
    out.write("Распознавание QR-кода...\n")
    out.flush()
    
    try:
        qr_url = detect_qr_code(image_bytes)
        
        if not qr_url:
            out.write("❌ QR-код не найден\n")
            sys.exit(1)
        
        out.write(f"✅ QR-код распознан!\n")
        out.write(f"URL: {qr_url}\n\n")
        out.flush()
        
        # Шаг 2: Получение данных чека
        out.write("Шаг 2: Получение данных чека со страницы\n")
        out.write("-"*80 + "\n")
        out.write("Переход по URL и парсинг страницы...\n")
        out.flush()
        
        scraped_data = scrape_receipt_data(qr_url)
        
        out.write("✅ Данные успешно получены!\n\n")
        out.flush()
        
        # Шаг 3: Вывод результатов
        out.write("Шаг 3: РЕЗУЛЬТАТЫ\n")
        out.write("="*80 + "\n\n")
        
        out.write("ОСНОВНАЯ ИНФОРМАЦИЯ:\n")
        out.write(f"  Торговец: {scraped_data.get('merchant', 'не определен')}\n")
        out.write(f"  Дата покупки: {scraped_data.get('purchase_ts', 'не определена')}\n")
        
        total = scraped_data.get('total')
        if total:
            out.write(f"  Общая сумма: {total / 100:.2f} грн ({total} копеек)\n")
        else:
            out.write(f"  Общая сумма: не определена\n")
        
        line_items = scraped_data.get('line_items', [])
        out.write(f"\nПОЗИЦИИ ЧЕКА ({len(line_items)}):\n")
        out.write("-"*80 + "\n")
        
        if not line_items:
            out.write("  ⚠️  Позиции не найдены\n")
        else:
            for i, item in enumerate(line_items, 1):
                price = item.get('price', 0)
                price_uah = price / 100 if price else 0
                quantity = item.get('quantity', 1)
                name = item.get('name', 'неизвестно')
                
                out.write(f"\n  {i}. {name}\n")
                out.write(f"     Количество: {quantity} шт.\n")
                out.write(f"     Цена за единицу: {price_uah:.2f} грн ({price} копеек)\n")
                if quantity > 1:
                    total_item = price * quantity
                    out.write(f"     Итого за позицию: {total_item / 100:.2f} грн ({total_item} копеек)\n")
        
        # Сохранение JSON
        payload_for_json = json.loads(json.dumps(scraped_data, default=str))
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(payload_for_json, f, indent=2, ensure_ascii=False)
        
        out.write("\n" + "="*80 + "\n")
        out.write("✅ Обработка завершена успешно!\n")
        out.write(f"Результат сохранен в: {output_file}\n")
        out.write(f"JSON данные сохранены в: {json_file}\n")
        
    except Exception as e:
        out.write(f"\n❌ Ошибка: {e}\n")
        import traceback
        traceback.print_exc(file=out)
        sys.exit(1)

print(f"Результат сохранен в: {output_file}")

