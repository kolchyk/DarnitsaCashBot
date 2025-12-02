#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path

# Настройка путей
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
os.environ.setdefault("ENCRYPTION_SECRET", "dummy_secret")

# Импорт функции распознавания
from services.ocr_worker.qr_scanner import detect_qr_code

# Чтение изображения
image_file = project_root / "5292124673841762126.jpg"
print(f"Чтение файла: {image_file}")

with open(image_file, "rb") as f:
    image_bytes = f.read()

print(f"Размер изображения: {len(image_bytes):,} байт")
print("Распознавание QR-кода с помощью QReader...")
print("(При первом запуске может занять время для загрузки моделей)")

try:
    qr_url = detect_qr_code(image_bytes)
    
    if qr_url:
        print("\n" + "="*80)
        print("✅ QR-КОД УСПЕШНО РАСПОЗНАН!")
        print("="*80)
        print(f"\nURL из QR-кода:")
        print(f"  {qr_url}")
        print(f"\nДлина: {len(qr_url)} символов")
        
        if qr_url.startswith("http://") or qr_url.startswith("https://"):
            print(f"Тип: URL")
            print(f"Протокол: {'HTTPS' if qr_url.startswith('https') else 'HTTP'}")
        
        # Сохраняем результат в файл
        result_file = project_root / "qr_result.txt"
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(qr_url)
        print(f"\nРезультат сохранен в: {result_file}")
    else:
        print("\n❌ QR-код не найден в изображении")
        
except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

