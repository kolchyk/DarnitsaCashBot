#!/usr/bin/env python3
"""Debug script for QR code detection - tests multiple methods."""

import sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from io import BytesIO

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_opencv_qr(image_bytes: bytes):
    """Test OpenCV QR detection with various preprocessing."""
    print("\n" + "="*80)
    print("TESTING OPENCV QR DETECTION")
    print("="*80)
    
    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if image is None:
        pil_image = Image.open(BytesIO(image_bytes))
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        image_array = np.array(pil_image)
        image = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
    
    print(f"Image shape: {image.shape}")
    print(f"Image dtype: {image.dtype}")
    print(f"Image min/max: {image.min()}/{image.max()}")
    
    qr_detector = cv2.QRCodeDetector()
    
    # Test 1: Original image
    print("\n[1] Testing original image...")
    retval, decoded_info, points = qr_detector.detectAndDecode(image)
    if retval and decoded_info is not None:
        decoded_str = str(decoded_info) if not isinstance(decoded_info, str) else decoded_info
        if len(decoded_str) > 0:
            print(f"  ✅ SUCCESS: {decoded_str[:100]}")
            return decoded_str
    print(f"  ❌ Failed (retval={retval})")
    
    # Helper function to check decoded_info
    def check_decoded(retval, decoded_info):
        if not retval or decoded_info is None:
            return None
        decoded_str = str(decoded_info) if not isinstance(decoded_info, str) else decoded_info
        return decoded_str if len(decoded_str) > 0 else None
    
    # Test 2: Grayscale
    print("\n[2] Testing grayscale...")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    retval, decoded_info, points = qr_detector.detectAndDecode(gray)
    result = check_decoded(retval, decoded_info)
    if result:
        print(f"  ✅ SUCCESS: {result[:100]}")
        return result
    print(f"  ❌ Failed (retval={retval})")
    if points is not None and len(points) > 0:
        print(f"  Points detected: {points.shape}")
    
    # Test 3: CLAHE
    print("\n[3] Testing CLAHE enhancement...")
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    retval, decoded_info, points = qr_detector.detectAndDecode(enhanced)
    result = check_decoded(retval, decoded_info)
    if result:
        print(f"  ✅ SUCCESS: {result[:100]}")
        return result
    print(f"  ❌ Failed (retval={retval})")
    
    # Test 4: OTSU Threshold
    print("\n[4] Testing OTSU threshold...")
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    retval, decoded_info, points = qr_detector.detectAndDecode(thresh)
    result = check_decoded(retval, decoded_info)
    if result:
        print(f"  ✅ SUCCESS: {result[:100]}")
        return result
    print(f"  ❌ Failed (retval={retval})")
    
    # Test 5: Adaptive threshold
    print("\n[5] Testing adaptive threshold...")
    adaptive_thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    retval, decoded_info, points = qr_detector.detectAndDecode(adaptive_thresh)
    result = check_decoded(retval, decoded_info)
    if result:
        print(f"  ✅ SUCCESS: {result[:100]}")
        return result
    print(f"  ❌ Failed (retval={retval})")
    
    # Test 6: Inverted
    print("\n[6] Testing inverted image...")
    inverted = cv2.bitwise_not(gray)
    retval, decoded_info, points = qr_detector.detectAndDecode(inverted)
    result = check_decoded(retval, decoded_info)
    if result:
        print(f"  ✅ SUCCESS: {result[:100]}")
        return result
    print(f"  ❌ Failed (retval={retval})")
    
    # Test 7: Resized (scale up)
    print("\n[7] Testing resized image (2x)...")
    height, width = gray.shape[:2]
    resized = cv2.resize(gray, (width*2, height*2), interpolation=cv2.INTER_CUBIC)
    retval, decoded_info, points = qr_detector.detectAndDecode(resized)
    result = check_decoded(retval, decoded_info)
    if result:
        print(f"  ✅ SUCCESS: {result[:100]}")
        return result
    print(f"  ❌ Failed (retval={retval})")
    
    # Test 8: Multi detection
    print("\n[8] Testing multi detection...")
    try:
        retval, decoded_info, points, straight_qrcode = qr_detector.detectAndDecodeMulti(image)
        if retval and decoded_info is not None:
            if isinstance(decoded_info, list) and len(decoded_info) > 0:
                qr_data = decoded_info[0]
            else:
                qr_data = decoded_info
            result = check_decoded(True, qr_data)
            if result:
                print(f"  ✅ SUCCESS: {result[:100]}")
                return result
        print(f"  ❌ Failed (retval={retval})")
    except Exception as e:
        print(f"  ❌ Multi detection not available: {e}")
    
    return None


def test_pyzbar(image_bytes: bytes):
    """Test pyzbar QR detection."""
    print("\n" + "="*80)
    print("TESTING PYZBAR QR DETECTION")
    print("="*80)
    
    try:
        from pyzbar.pyzbar import decode
        
        # Decode image
        pil_image = Image.open(BytesIO(image_bytes))
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        
        # Try original
        print("\n[1] Testing original image...")
        decoded = decode(pil_image)
        if decoded:
            qr_data = decoded[0].data.decode('utf-8')
            print(f"  ✅ SUCCESS: {qr_data[:100]}")
            return qr_data
        print("  ❌ Failed")
        
        # Try grayscale
        print("\n[2] Testing grayscale...")
        gray_image = pil_image.convert('L')
        decoded = decode(gray_image)
        if decoded:
            qr_data = decoded[0].data.decode('utf-8')
            print(f"  ✅ SUCCESS: {qr_data[:100]}")
            return qr_data
        print("  ❌ Failed")
        
        # Try with numpy array (sometimes works better)
        print("\n[3] Testing numpy array conversion...")
        img_array = np.array(pil_image)
        decoded = decode(img_array)
        if decoded:
            qr_data = decoded[0].data.decode('utf-8')
            print(f"  ✅ SUCCESS: {qr_data[:100]}")
            return qr_data
        print("  ❌ Failed")
        
        return None
    except ImportError:
        print("  ⚠️  pyzbar not installed")
        return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_qr_detection.py <image_file>")
        return 1
    
    image_file = Path(sys.argv[1])
    if not image_file.exists():
        print(f"❌ File not found: {image_file}")
        return 1
    
    print(f"📄 File: {image_file}")
    print(f"📊 Size: {image_file.stat().st_size:,} bytes")
    
    with open(image_file, "rb") as f:
        image_bytes = f.read()
    
    # Test OpenCV
    result = test_opencv_qr(image_bytes)
    if result:
        print(f"\n✅ QR CODE FOUND: {result}")
        return 0
    
    # Test pyzbar
    result = test_pyzbar(image_bytes)
    if result:
        print(f"\n✅ QR CODE FOUND: {result}")
        return 0
    
    # Try cropping QR code area (usually in center/middle of receipt)
    print("\n" + "="*80)
    print("TESTING WITH QR CODE CROP")
    print("="*80)
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        pil_image = Image.open(BytesIO(image_bytes))
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        image_array = np.array(pil_image)
        image = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
    
    height, width = image.shape[:2]
    # QR codes are usually in the middle section of receipts
    # Try cropping middle 60% vertically and full width
    y_start = int(height * 0.2)
    y_end = int(height * 0.8)
    cropped = image[y_start:y_end, :]
    
    print(f"Cropped image shape: {cropped.shape}")
    cropped_bytes = cv2.imencode('.jpg', cropped)[1].tobytes()
    
    result = test_opencv_qr(cropped_bytes)
    if result:
        print(f"\n✅ QR CODE FOUND IN CROPPED IMAGE: {result}")
        return 0
    
    result = test_pyzbar(cropped_bytes)
    if result:
        print(f"\n✅ QR CODE FOUND IN CROPPED IMAGE: {result}")
        return 0
    
    print("\n❌ QR CODE NOT FOUND WITH ANY METHOD")
    print("\n💡 SUGGESTIONS:")
    print("  1. Check if QR code is clearly visible in the image")
    print("  2. Try taking a higher resolution photo")
    print("  3. Ensure QR code is not damaged or obscured")
    print("  4. Try manual QR code scanning with a phone app")
    return 1


if __name__ == "__main__":
    sys.exit(main())

