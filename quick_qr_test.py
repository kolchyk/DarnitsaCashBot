import sys
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
os.environ.setdefault("ENCRYPTION_SECRET", "dummy_secret")

print("Loading QR scanner...")
from services.ocr_worker.qr_scanner import detect_qr_code

print("Reading image file...")
with open("5292124673841762126.jpg", "rb") as f:
    image_bytes = f.read()

print(f"Image loaded: {len(image_bytes)} bytes")
print("Detecting QR code (this may take a moment on first run as QReader loads models)...")

try:
    qr_url = detect_qr_code(image_bytes)
    if qr_url:
        print(f"\n✅ QR Code detected!")
        print(f"URL: {qr_url}")
    else:
        print("\n❌ QR Code not found")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

