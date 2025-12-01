#!/usr/bin/env python3
"""Диагностический скрипт для проверки настройки Tesseract в продакшене."""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_tesseract_setup():
    """Проверяет настройку Tesseract и языковых данных."""
    print("=" * 80)
    print("TESSERACT SETUP DIAGNOSTICS")
    print("=" * 80)
    
    # 1. Проверка бинарника Tesseract
    print("\n1. Checking Tesseract binary...")
    import shutil
    tesseract_cmd = shutil.which("tesseract")
    if tesseract_cmd:
        print(f"   ✓ Found: {tesseract_cmd}")
        # Проверяем версию
        import subprocess
        try:
            result = subprocess.run([tesseract_cmd, "--version"], 
                                  capture_output=True, text=True, timeout=5)
            version_line = result.stdout.split('\n')[0] if result.stdout else "unknown"
            print(f"   Version: {version_line}")
        except Exception as e:
            print(f"   ⚠ Could not get version: {e}")
    else:
        print("   ✗ Tesseract binary not found in PATH")
        # Проверяем стандартные пути
        common_paths = [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
            "/opt/homebrew/bin/tesseract",
        ]
        for path in common_paths:
            if Path(path).exists():
                print(f"   ✓ Found at: {path}")
                tesseract_cmd = path
                break
    
    # 2. Проверка TESSDATA_PREFIX
    print("\n2. Checking TESSDATA_PREFIX...")
    tessdata_prefix = os.environ.get("TESSDATA_PREFIX")
    if tessdata_prefix:
        print(f"   Environment variable: {tessdata_prefix}")
    else:
        print("   ⚠ TESSDATA_PREFIX not set in environment")
    
    # 3. Проверка возможных путей к tessdata
    print("\n3. Checking tessdata directories...")
    possible_paths = [
        Path("tessdata_final"),  # Relative to CWD
        Path.cwd() / "tessdata_final",
        project_root / "tessdata_final",
        Path("/usr/share/tesseract-ocr/5/tessdata"),
        Path("/usr/share/tesseract-ocr/tessdata"),
    ]
    
    if tessdata_prefix:
        possible_paths.insert(0, Path(tessdata_prefix))
    
    found_paths = []
    for path in possible_paths:
        if path.exists():
            print(f"   ✓ Found: {path.absolute()}")
            found_paths.append(path)
            # Проверяем языковые файлы
            lang_files = list(path.glob("*.traineddata"))
            if lang_files:
                lang_names = [f.stem for f in lang_files]
                print(f"      Languages: {', '.join(sorted(lang_names))}")
                # Проверяем наличие украинского
                if "ukr" in lang_names:
                    print(f"      ✓ Ukrainian (ukr) language file found")
                else:
                    print(f"      ✗ Ukrainian (ukr) language file NOT found")
            else:
                print(f"      ⚠ No .traineddata files found")
    
    if not found_paths:
        print("   ✗ No tessdata directories found")
    
    # 4. Проверка через pytesseract
    print("\n4. Testing pytesseract...")
    try:
        import pytesseract
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        # Устанавливаем TESSDATA_PREFIX если нашли путь
        if found_paths and not tessdata_prefix:
            os.environ["TESSDATA_PREFIX"] = str(found_paths[0])
            print(f"   Set TESSDATA_PREFIX to: {found_paths[0]}")
        
        # Проверяем доступные языки
        try:
            langs = pytesseract.get_languages()
            print(f"   ✓ Available languages: {', '.join(sorted(langs))}")
            if "ukr" in langs:
                print(f"   ✓ Ukrainian (ukr) is available")
            else:
                print(f"   ✗ Ukrainian (ukr) is NOT available")
        except Exception as e:
            print(f"   ✗ Error getting languages: {e}")
        
    except ImportError:
        print("   ✗ pytesseract not installed")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # 5. Проверка настроек проекта
    print("\n5. Checking project settings...")
    try:
        from libs.common import get_settings
        settings = get_settings()
        print(f"   OCR_LANGUAGES: {settings.ocr_languages}")
        print(f"   TESSERACT_CMD: {settings.tesseract_cmd or 'not set'}")
        print(f"   TESSDATA_DIR: {settings.tessdata_dir or 'not set'}")
    except Exception as e:
        print(f"   ⚠ Could not load settings: {e}")
    
    # 6. Проверка исходной директории tessdata
    print("\n6. Checking source tessdata directory...")
    source_tessdata = project_root / "tessdata"
    if source_tessdata.exists():
        print(f"   ✓ Found: {source_tessdata}")
        lang_files = list(source_tessdata.glob("*.traineddata"))
        if lang_files:
            lang_names = [f.stem for f in lang_files]
            print(f"   Languages in source: {', '.join(sorted(lang_names))}")
        else:
            print(f"   ⚠ No .traineddata files in source directory")
    else:
        print(f"   ✗ Source tessdata directory not found: {source_tessdata}")
    
    print("\n" + "=" * 80)
    print("DIAGNOSTICS COMPLETE")
    print("=" * 80)
    
    # Рекомендации
    print("\nRECOMMENDATIONS:")
    if not found_paths:
        print("  - Ensure tessdata_final directory exists and contains language files")
        print("  - Check that post_compile script runs successfully")
    elif "ukr" not in [f.stem for p in found_paths for f in p.glob("*.traineddata")]:
        print("  - Ukrainian language file (ukr.traineddata) is missing")
        print("  - Ensure tessdata/ukr.traineddata exists and is copied to tessdata_final")
    if not tessdata_prefix and found_paths:
        print(f"  - Set TESSDATA_PREFIX environment variable to: {found_paths[0]}")
    
    return 0

if __name__ == "__main__":
    sys.exit(check_tesseract_setup())

