from __future__ import annotations

import logging
from io import BytesIO

from PIL import Image
from pyzbar import pyzbar

LOGGER = logging.getLogger(__name__)


class QRCodeNotFoundError(Exception):
    """Raised when QR code cannot be found in the image."""


def detect_qr_code(image_bytes: bytes) -> str | None:
    """
    Detect QR code in image using pyzbar.
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        URL string from QR code, or None if not found
        
    Raises:
        QRCodeNotFoundError: If QR code cannot be detected
    """
    LOGGER.debug("Starting QR code detection: image_size=%d bytes", len(image_bytes))
    
    try:
        # Decode image to PIL Image
        image = _decode_image(image_bytes)
        if image is None:
            raise QRCodeNotFoundError("Failed to decode image")
        
        LOGGER.debug("Image decoded: size=%s, mode=%s", image.size, image.mode)
        
        # Use pyzbar for detection
        decoded_objects = pyzbar.decode(image)
        
        if decoded_objects:
            # Process all found QR codes, return the first valid one
            for decoded in decoded_objects:
                if decoded.type == 'QRCODE':
                    try:
                        # Decode bytes to string
                        qr_data = decoded.data.decode('utf-8')
                        LOGGER.info(
                            "QR code detected with pyzbar: data_length=%d, data_preview=%s",
                            len(qr_data),
                            qr_data[:50],
                        )
                        return qr_data
                    except UnicodeDecodeError as e:
                        LOGGER.warning("Failed to decode QR code data as UTF-8: %s", e)
                        continue
        
        LOGGER.warning("No QR codes found in image")
        return None
            
    except QRCodeNotFoundError:
        raise
    except Exception as e:
        LOGGER.error("Error detecting QR code: %s", e, exc_info=True)
        raise QRCodeNotFoundError(f"Failed to detect QR code: {str(e)}") from e


def _decode_image(image_bytes: bytes) -> Image.Image | None:
    """
    Decode image bytes to PIL Image.
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        PIL Image object, or None if decoding fails
    """
    try:
        # Load image from bytes using PIL
        image = Image.open(BytesIO(image_bytes))
        
        # Convert to grayscale for better QR code recognition
        # pyzbar works better with grayscale images
        if image.mode != 'L':
            image = image.convert('L')
        
        return image
        
    except Exception as e:
        LOGGER.error("Failed to decode image: %s", e)
        return None

