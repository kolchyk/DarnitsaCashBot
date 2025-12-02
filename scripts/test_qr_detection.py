#!/usr/bin/env python3
"""Тест распознавания QR-кода с использованием QReader.

Этот скрипт тестирует только детекцию QR-кода на изображении чека.
Использует QReader (YOLOv8 + Pyzbar) для максимально надежного распознавания.

Использование:
    python scripts/test_qr_detection.py [путь_к_файлу.jpg]
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from services.ocr_worker.qr_scanner import detect_qr_code, QRCodeNotFoundError
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("\n📦 Установите необходимые зависимости:")
    print("   poetry install")
    print("   или")
    print("   pip install qreader opencv-python-headless pillow numpy")
    sys.exit(1)


def print_section(title: str, char: str = "="):
    """Печатает заголовок секции."""
    print("\n" + char * 80)
    print(f"  {title}")
    print(char * 80)


def main():
    """Основная функция тестирования QR-кода."""
    # Инициализация настроек (минимальные для работы)
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
    os.environ.setdefault("ENCRYPTION_SECRET", "dummy_secret")
    
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
        print("\nПримеры:")
        print(f"  python {sys.argv[0]} check.jpg")
        print(f"  python {sys.argv[0]} /path/to/receipt.jpg")
        return 1
    
    print_section("🔍 ТЕСТИРОВАНИЕ РАСПОЗНАВАНИЯ QR-КОДА (QReader)", "=")
    print(f"📄 Файл: {image_file}")
    print(f"📅 Время: {datetime.now().isoformat()}")
    print(f"🔧 Библиотека: QReader (YOLOv8 + Pyzbar)")
    
    # Шаг 1: Чтение изображения
    print_section("Шаг 1: Загрузка изображения")
    try:
        with open(image_file, "rb") as f:
            image_bytes = f.read()
        file_size_kb = len(image_bytes) / 1024
        print(f"✅ Файл успешно загружен")
        print(f"   Размер: {len(image_bytes):,} байт ({file_size_kb:.2f} KB)")
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Шаг 2: Распознавание QR-кода
    print_section("Шаг 2: Распознавание QR-кода с QReader")
    try:
        print("⏳ Обработка изображения...")
        qr_url = detect_qr_code(image_bytes)
        
        if not qr_url:
            print("❌ QR-код не найден в изображении")
            print("\n💡 Возможные причины:")
            print("   - QR-код отсутствует на изображении")
            print("   - Изображение слишком низкого качества")
            print("   - QR-код поврежден или неполный")
            return 1
        
        print(f"✅ QR-код успешно распознан!")
        print(f"\n📋 РЕЗУЛЬТАТ:")
        print(f"   URL: {qr_url}")
        print(f"   Длина: {len(qr_url)} символов")
        
        # Проверяем, является ли это URL
        if qr_url.startswith("http://") or qr_url.startswith("https://"):
            print(f"   Тип: URL (веб-ссылка)")
            print(f"   Протокол: {'HTTPS' if qr_url.startswith('https') else 'HTTP'}")
        else:
            print(f"   Тип: Текст (не URL)")
        
        # Показываем превью URL
        if len(qr_url) > 100:
            preview = qr_url[:97] + "..."
        else:
            preview = qr_url
        print(f"\n   Превью: {preview}")
        
    except QRCodeNotFoundError as e:
        print(f"❌ Ошибка: QR-код не найден - {e}")
        print("\n💡 QReader не смог обнаружить QR-код на изображении.")
        return 1
    except Exception as e:
        print(f"❌ Ошибка распознавания QR-кода: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Шаг 3: Дополнительная информация
    print_section("Шаг 3: Дополнительная информация")
    print("✅ Тест завершен успешно!")
    print("\n📝 Примечания:")
    print("   - QReader использует YOLOv8 для локализации QR-кода")
    print("   - Затем применяет Pyzbar для декодирования")
    print("   - Это наиболее надежный метод для сложных изображений")
    
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

