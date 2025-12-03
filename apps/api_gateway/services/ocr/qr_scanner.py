from __future__ import annotations

import importlib
import logging
from io import BytesIO
from typing import Iterable

import numpy as np
from PIL import Image, ImageFilter, ImageOps

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
        original_image = Image.open(BytesIO(image_bytes))
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.error("Failed to decode QR image bytes: %s", exc, exc_info=True)
        raise QRCodeNotFoundError("Failed to decode image") from exc

    LOGGER.debug("Image decoded: size=%s, mode=%s", original_image.size, original_image.mode)

    variant_count = 0
    for variant_name, candidate in _iter_processed_images(original_image):
        variant_count += 1
        LOGGER.debug("Trying QR detection variant %d: %s (size=%s, mode=%s)", 
                     variant_count, variant_name, candidate.size, candidate.mode)
        
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
                "QR code detected with pyzbar (variant: %s): data_length=%d, data_preview=%s",
                variant_name,
                len(qr_data),
                qr_data[:50],
            )
            return qr_data

    LOGGER.warning("No QR codes found in image after trying %d variants", variant_count)
    return None


def _apply_threshold_otsu(image: Image.Image) -> Image.Image:
    """Apply OTSU thresholding for binarization."""
    if image.mode != "L":
        image = image.convert("L")
    
    # Convert to numpy array for OTSU thresholding
    img_array = np.array(image)
    
    # Calculate OTSU threshold
    hist, bins = np.histogram(img_array.flatten(), 256, [0, 256])
    hist = hist.astype(float)
    
    # Normalize histogram
    hist /= hist.sum()
    
    # Calculate cumulative sums and means
    cumsum = np.cumsum(hist)
    cummean = np.cumsum(hist * np.arange(256))
    
    # Calculate between-class variance for all thresholds
    between_class_variance = np.zeros(256)
    for t in range(256):
        w0 = cumsum[t]
        w1 = 1.0 - w0
        if w0 == 0 or w1 == 0:
            continue
        m0 = cummean[t] / w0 if w0 > 0 else 0
        m1 = (cummean[255] - cummean[t]) / w1 if w1 > 0 else 0
        between_class_variance[t] = w0 * w1 * (m0 - m1) ** 2
    
    # Find threshold with maximum variance
    threshold = np.argmax(between_class_variance)
    
    # Apply threshold
    binary = (img_array > threshold).astype(np.uint8) * 255
    return Image.fromarray(binary, mode="L")


def _apply_threshold_adaptive(image: Image.Image, block_size: int = 11, c: int = 2) -> Image.Image:
    """Apply adaptive thresholding for binarization."""
    if image.mode != "L":
        image = image.convert("L")
    
    img_array = np.array(image, dtype=np.float32)
    h, w = img_array.shape
    
    # Use convolution for faster local mean calculation
    # Create a simple box filter kernel
    kernel_size = block_size
    kernel = np.ones((kernel_size, kernel_size), dtype=np.float32) / (kernel_size * kernel_size)
    
    # Pad image for convolution
    pad = kernel_size // 2
    padded = np.pad(img_array, pad, mode='edge')
    
    # Calculate local mean using convolution (simplified)
    # For better performance, use a simpler approach with scipy if available
    # For now, use a more efficient sliding window approach
    mean_img = np.zeros_like(img_array)
    half_block = block_size // 2
    
    # Optimize: only calculate mean for a subset if image is very large
    if h * w > 1000000:  # For very large images, use a faster approximation
        # Use downsampled version for mean calculation
        step = 2
        for y in range(0, h, step):
            for x in range(0, w, step):
                y1 = max(0, y - half_block)
                y2 = min(h, y + half_block + 1)
                x1 = max(0, x - half_block)
                x2 = min(w, x + half_block + 1)
                local_mean = np.mean(img_array[y1:y2, x1:x2])
                # Fill a small region with this mean
                y_end = min(h, y + step)
                x_end = min(w, x + step)
                mean_img[y:y_end, x:x_end] = local_mean
    else:
        # Full calculation for smaller images
        for y in range(h):
            for x in range(w):
                y1 = max(0, y - half_block)
                y2 = min(h, y + half_block + 1)
                x1 = max(0, x - half_block)
                x2 = min(w, x + half_block + 1)
                mean_img[y, x] = np.mean(img_array[y1:y2, x1:x2])
    
    # Apply adaptive threshold
    binary = ((img_array > (mean_img - c)) * 255).astype(np.uint8)
    return Image.fromarray(binary, mode="L")


def _apply_threshold_simple(image: Image.Image, threshold: int = 128) -> Image.Image:
    """Apply simple thresholding for binarization."""
    if image.mode != "L":
        image = image.convert("L")
    
    img_array = np.array(image)
    binary = ((img_array > threshold) * 255).astype(np.uint8)
    return Image.fromarray(binary, mode="L")


def _apply_sharpen(image: Image.Image) -> Image.Image:
    """Apply sharpening filter to enhance QR code edges."""
    return image.filter(ImageFilter.SHARPEN)


def _apply_denoise(image: Image.Image) -> Image.Image:
    """Apply denoising filter to remove artifacts."""
    # Use median filter for denoising
    return image.filter(ImageFilter.MedianFilter(size=3))


def _iter_processed_images(original_image: Image.Image) -> Iterable[tuple[str, Image.Image]]:
    """
    Generate image variations to improve QR detection success.
    
    Yields:
        Tuple of (variant_name, processed_image) for logging purposes.
    """
    
    # Base preprocessing: grayscale + autocontrast
    grayscale = original_image.convert("L") if original_image.mode != "L" else original_image
    base_image = ImageOps.autocontrast(grayscale)
    
    # 1. Original grayscale + autocontrast
    yield ("grayscale_autocontrast", base_image)
    
    # 2. Grayscale + autocontrast + sharpen
    sharpened = _apply_sharpen(base_image)
    yield ("grayscale_autocontrast_sharpened", sharpened)
    
    # 3. Grayscale + autocontrast + denoise
    denoised = _apply_denoise(base_image)
    yield ("grayscale_autocontrast_denoised", denoised)
    
    # 4. OTSU thresholding (binary)
    otsu = _apply_threshold_otsu(base_image)
    yield ("otsu_threshold", otsu)
    
    # 5. OTSU + sharpen
    otsu_sharp = _apply_sharpen(otsu)
    yield ("otsu_threshold_sharpened", otsu_sharp)
    
    # 6. Adaptive thresholding
    adaptive = _apply_threshold_adaptive(base_image)
    yield ("adaptive_threshold", adaptive)
    
    # 7. Adaptive threshold + sharpen
    adaptive_sharp = _apply_sharpen(adaptive)
    yield ("adaptive_threshold_sharpened", adaptive_sharp)
    
    # 8. Simple threshold (128)
    simple = _apply_threshold_simple(base_image, threshold=128)
    yield ("simple_threshold_128", simple)
    
    # 9. Simple threshold (100) - darker threshold
    simple_dark = _apply_threshold_simple(base_image, threshold=100)
    yield ("simple_threshold_100", simple_dark)
    
    # 10. Simple threshold (150) - lighter threshold
    simple_light = _apply_threshold_simple(base_image, threshold=150)
    yield ("simple_threshold_150", simple_light)
    
    # Try RGB mode (sometimes works better for colored QR codes)
    if original_image.mode != "L":
        rgb_base = ImageOps.autocontrast(original_image)
        yield ("rgb_autocontrast", rgb_base)
        
        # RGB + sharpen
        rgb_sharp = _apply_sharpen(rgb_base)
        yield ("rgb_autocontrast_sharpened", rgb_sharp)
    
    # Scaling variants with different preprocessing
    scale_factors = [1.5, 2.0, 3.0]
    for scale in scale_factors:
        scaled = base_image.resize(
            (int(base_image.width * scale), int(base_image.height * scale)),
            Image.Resampling.LANCZOS
        )
        yield (f"scaled_{scale}x_grayscale", scaled)
        
        # Scaled + OTSU
        scaled_otsu = _apply_threshold_otsu(scaled)
        yield (f"scaled_{scale}x_otsu", scaled_otsu)
        
        # Scaled + sharpen
        scaled_sharp = _apply_sharpen(scaled)
        yield (f"scaled_{scale}x_sharpened", scaled_sharp)
        
        # Scaled + OTSU + sharpen
        scaled_otsu_sharp = _apply_sharpen(scaled_otsu)
        yield (f"scaled_{scale}x_otsu_sharpened", scaled_otsu_sharp)
    
    # Rotated variants (for sideways photos) - try with best preprocessing
    for angle in (90, 180, 270):
        rotated = base_image.rotate(angle, expand=True)
        yield (f"rotated_{angle}_grayscale", rotated)
        
        # Rotated + OTSU
        rotated_otsu = _apply_threshold_otsu(rotated)
        yield (f"rotated_{angle}_otsu", rotated_otsu)
        
        # Rotated + sharpen
        rotated_sharp = _apply_sharpen(rotated)
        yield (f"rotated_{angle}_sharpened", rotated_sharp)


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

