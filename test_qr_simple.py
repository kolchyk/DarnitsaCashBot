import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.ocr_worker.qr_scanner import detect_qr_code

image_file = project_root / "5292124673841762126.jpg"

print(f"Loading image: {image_file}")
with open(image_file, "rb") as f:
    image_bytes = f.read()

print(f"Image size: {len(image_bytes)} bytes")
print("Detecting QR code...")

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

