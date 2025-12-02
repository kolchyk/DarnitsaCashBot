#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Устанавливаем переменные окружения
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
os.environ.setdefault("ENCRYPTION_SECRET", "dummy_secret")

from services.ocr_worker.qr_scanner import detect_qr_code, QRCodeNotFoundError

def main():
    image_file = project_root / "5292124673841762126.jpg"
    
    print("=" * 80)
    print("QR Code Detection Test")
    print("=" * 80)
    print(f"Image file: {image_file}")
    
    if not image_file.exists():
        print(f"ERROR: File not found: {image_file}")
        return 1
    
    # Читаем изображение
    print("\nLoading image...")
    with open(image_file, "rb") as f:
        image_bytes = f.read()
    
    print(f"Image size: {len(image_bytes):,} bytes ({len(image_bytes) / 1024:.2f} KB)")
    
    # Детектируем QR-код
    print("\nDetecting QR code with QReader...")
    try:
        qr_url = detect_qr_code(image_bytes)
        
        if qr_url:
            print("\n" + "=" * 80)
            print("✅ SUCCESS: QR Code detected!")
            print("=" * 80)
            print(f"\nQR Code content:")
            print(f"  URL: {qr_url}")
            print(f"  Length: {len(qr_url)} characters")
            
            if qr_url.startswith("http://") or qr_url.startswith("https://"):
                print(f"  Type: URL")
                print(f"  Protocol: {'HTTPS' if qr_url.startswith('https') else 'HTTP'}")
            
            # Показываем превью
            if len(qr_url) > 100:
                preview = qr_url[:97] + "..."
            else:
                preview = qr_url
            print(f"\n  Preview: {preview}")
            print("=" * 80)
            return 0
        else:
            print("\n" + "=" * 80)
            print("❌ FAILED: QR Code not found in image")
            print("=" * 80)
            return 1
            
    except QRCodeNotFoundError as e:
        print("\n" + "=" * 80)
        print(f"❌ ERROR: {e}")
        print("=" * 80)
        return 1
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ UNEXPECTED ERROR: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

