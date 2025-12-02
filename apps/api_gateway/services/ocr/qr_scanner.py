from __future__ import annotations

import logging
from io import BytesIO

import numpy as np
from PIL import Image
from qreader import QReader

LOGGER = logging.getLogger(__name__)


class QRCodeNotFoundError(Exception):
    """Raised when QR code cannot be found in the image."""


def detect_qr_code(image_bytes: bytes) -> str | None:
    """
    Detect QR code in image using QReader (YOLOv8 + Pyzbar).
    QReader is the most robust solution for detecting QR codes in challenging or low-quality images.
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        URL string from QR code, or None if not found
        
    Raises:
        QRCodeNotFoundError: If QR code cannot be detected
    """
    LOGGER.debug("Starting QR code detection: image_size=%d bytes", len(image_bytes))
    
    try:
        # Decode image to numpy array (RGB format for QReader)
        image = _decode_image(image_bytes)
        if image is None:
            raise QRCodeNotFoundError("Failed to decode image")
        
        LOGGER.debug("Image decoded: shape=%s", image.shape)
        
        # Use QReader for detection
        qreader = QReader()
        decoded_text = qreader.detect_and_decode(image)
        
        if decoded_text:
            # QReader might return a string, tuple, or a list
            if isinstance(decoded_text, tuple):
                # Extract first element from tuple if it's not empty
                decoded_text = decoded_text[0] if decoded_text else None
            
            if isinstance(decoded_text, list):
                # If multiple QR codes found, return the first valid one
                for text in decoded_text:
                    if text:
                        LOGGER.info("QR code detected with QReader: data_length=%d, data_preview=%s", len(text), text[:50])
                        return str(text)
            elif decoded_text:
                # Single string result
                result_str = str(decoded_text)
                LOGGER.info("QR code detected with QReader: data_length=%d, data_preview=%s", len(result_str), result_str[:50])
                return result_str
        
        LOGGER.warning("No QR codes found in image")
        return None
            
    except QRCodeNotFoundError:
        raise
    except Exception as e:
        LOGGER.error("Error detecting QR code: %s", e, exc_info=True)
        raise QRCodeNotFoundError(f"Failed to detect QR code: {str(e)}") from e


def _decode_image(image_bytes: bytes) -> np.ndarray | None:
    """
    Decode image bytes to numpy array in RGB format (required by QReader).
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        numpy array in RGB format, or None if decoding fails
    """
    try:
        pil_image = Image.open(BytesIO(image_bytes))
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        
        # Convert PIL Image to numpy array
        image_rgb = np.array(pil_image)
        return image_rgb
        
    except Exception as e:
        LOGGER.error("Failed to decode image: %s", e)
        return None

