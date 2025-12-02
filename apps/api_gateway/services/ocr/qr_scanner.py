from __future__ import annotations

import importlib
import logging
from io import BytesIO
from typing import Iterable

from PIL import Image, ImageOps

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

    decode_fn = _get_decoder()

    try:
        image = _decode_image(image_bytes)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.error("Failed to decode QR image bytes: %s", exc, exc_info=True)
        raise QRCodeNotFoundError("Failed to decode image") from exc

    LOGGER.debug("Image decoded: size=%s, mode=%s", image.size, image.mode)

    for candidate in _iter_processed_images(image):
        decoded_objects = decode_fn(candidate)

        if not decoded_objects:
            continue

        for decoded in decoded_objects:
            if decoded.type != "QRCODE":
                continue

            try:
                qr_data = decoded.data.decode("utf-8")
            except UnicodeDecodeError as exc:
                LOGGER.warning("Failed to decode QR code data as UTF-8: %s", exc)
                continue

            LOGGER.info(
                "QR code detected with pyzbar: data_length=%d, data_preview=%s",
                len(qr_data),
                qr_data[:50],
            )
            return qr_data

    LOGGER.warning("No QR codes found in image")
    return None


def _decode_image(image_bytes: bytes) -> Image.Image:
    """
    Decode image bytes to PIL Image.
    
    Args:
        image_bytes: Raw image bytes
        
    Returns:
        PIL Image object, or None if decoding fails
    """
    image = Image.open(BytesIO(image_bytes))

    # Convert to grayscale for better QR code recognition
    if image.mode != "L":
        image = image.convert("L")

    # Normalize contrast to make QR zones more distinct
    image = ImageOps.autocontrast(image)
    return image


def _iter_processed_images(image: Image.Image) -> Iterable[Image.Image]:
    """Generate image variations to improve QR detection success."""

    # Original (grayscale + autocontrast already applied)
    yield image

    # Slightly enlarged version to help with low-resolution captures
    larger = image.resize((int(image.width * 1.25), int(image.height * 1.25)))
    yield larger

    # Try rotated variants for sideways photos
    for angle in (90, 180, 270):
        yield image.rotate(angle, expand=True)


def _get_decoder():
    """Import and return the pyzbar decode function with helpful errors."""

    try:
        pyzbar = importlib.import_module("pyzbar.pyzbar")
        return pyzbar.decode
    except ImportError as exc:  # pragma: no cover - environment dependent
        message = (
            "pyzbar/zbar dependency is missing. Install system library 'libzbar0' "
            "and ensure pyzbar is available to enable QR detection."
        )
        LOGGER.error(message)
        raise QRCodeNotFoundError(message) from exc

