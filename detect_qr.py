#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
os.environ.setdefault("ENCRYPTION_SECRET", "dummy_secret")

from services.ocr_worker.qr_scanner import detect_qr_code

image_file = project_root / "5292124673841762126.jpg"
output_file = project_root / "qr_detection_result.txt"

with open(output_file, "w", encoding="utf-8") as out:
    out.write("=" * 80 + "\n")
    out.write("QR Code Detection Test\n")
    out.write("=" * 80 + "\n")
    out.write(f"Image file: {image_file}\n\n")
    
    if not image_file.exists():
        out.write(f"ERROR: File not found: {image_file}\n")
        sys.exit(1)
    
    out.write("Loading image...\n")
    with open(image_file, "rb") as f:
        image_bytes = f.read()
    
    out.write(f"Image size: {len(image_bytes):,} bytes ({len(image_bytes) / 1024:.2f} KB)\n\n")
    out.write("Detecting QR code with QReader...\n")
    out.flush()
    
    try:
        qr_url = detect_qr_code(image_bytes)
        
        if qr_url:
            out.write("\n" + "=" * 80 + "\n")
            out.write("✅ SUCCESS: QR Code detected!\n")
            out.write("=" * 80 + "\n")
            out.write(f"\nQR Code content:\n")
            out.write(f"  URL: {qr_url}\n")
            out.write(f"  Length: {len(qr_url)} characters\n")
            
            if qr_url.startswith("http://") or qr_url.startswith("https://"):
                out.write(f"  Type: URL\n")
                out.write(f"  Protocol: {'HTTPS' if qr_url.startswith('https') else 'HTTP'}\n")
            
            preview = qr_url[:97] + "..." if len(qr_url) > 100 else qr_url
            out.write(f"\n  Preview: {preview}\n")
            out.write("=" * 80 + "\n")
        else:
            out.write("\n" + "=" * 80 + "\n")
            out.write("❌ FAILED: QR Code not found in image\n")
            out.write("=" * 80 + "\n")
            
    except Exception as e:
        out.write("\n" + "=" * 80 + "\n")
        out.write(f"❌ ERROR: {e}\n")
        out.write("=" * 80 + "\n")
        import traceback
        traceback.print_exc(file=out)

print(f"Result saved to: {output_file}")

