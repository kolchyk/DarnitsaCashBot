#!/usr/bin/env python
"""
Test script to verify QR code detection on actual receipt images.
Run from project root: python scripts/test_qr_direct.py [image_path]
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from apps.api_gateway.services.ocr.qr_scanner import detect_qr_code, QRCodeNotFoundError


def test_qr_detection(image_path: str) -> None:
    """Test QR code detection on a specific image."""
    path = Path(image_path)
    
    if not path.exists():
        print(f"❌ Error: File not found: {path}")
        return
    
    print(f"📷 Testing QR detection on: {path.name}")
    print(f"   File size: {path.stat().st_size / 1024:.1f} KB")
    print("-" * 60)
    
    # Read image bytes
    with open(path, "rb") as f:
        image_bytes = f.read()
    
    print(f"   Image bytes loaded: {len(image_bytes)} bytes")
    
    try:
        # Detect QR code
        qr_data = detect_qr_code(image_bytes)
        
        if qr_data:
            print(f"\n✅ QR Code DETECTED!")
            print(f"   Data length: {len(qr_data)} characters")
            print(f"\n📎 Extracted URL/Data:")
            print(f"   {qr_data}")
            
            # Validate URL format
            if "cabinet.tax.gov.ua" in qr_data:
                print(f"\n✅ URL format looks correct (cabinet.tax.gov.ua)")
            elif "tax.gov.ua" in qr_data:
                print(f"\n⚠️  URL contains tax.gov.ua but not cabinet subdomain")
            elif qr_data.startswith("http"):
                print(f"\n⚠️  URL detected but not tax.gov.ua domain")
            else:
                print(f"\n⚠️  QR data is not a URL")
                
        else:
            print(f"\n❌ QR Code NOT found in image")
            print("   Try with different image or check image quality")
            
    except QRCodeNotFoundError as e:
        print(f"\n❌ QR Code detection failed: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {type(e).__name__}: {e}")


def main() -> None:
    """Main entry point."""
    print("=" * 60)
    print("QR Code Detection Test Script")
    print("=" * 60)
    
    # Default test image
    default_image = PROJECT_ROOT / "5292124673841762126.jpg"
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    elif default_image.exists():
        image_path = str(default_image)
    else:
        print("Usage: python scripts/test_qr_direct.py [image_path]")
        print(f"\nNo image path provided and default image not found: {default_image}")
        return
    
    test_qr_detection(image_path)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

