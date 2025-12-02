from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)


class UnreadableImageError(RuntimeError):
    """Raised when the incoming payload cannot be processed."""


@dataclass
class Artifact:
    name: str
    content: bytes
    content_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreprocessResult:
    processed_image: np.ndarray
    crops: dict[str, np.ndarray]
    metadata: dict[str, Any]
    artifacts: list[Artifact]


def preprocess_image(image_bytes: bytes, *, save_intermediates: bool = True) -> PreprocessResult:
    LOGGER.debug("Starting image preprocessing: image_size=%d bytes, save_intermediates=%s", len(image_bytes), save_intermediates)
    
    image = _bytes_to_image(image_bytes)
    if image is None:
        raise UnreadableImageError("Failed to decode receipt image")

    original_width = int(image.shape[1])
    original_height = int(image.shape[0])
    LOGGER.debug("Decoded image: %dx%d pixels, channels=%d", original_width, original_height, image.shape[2] if len(image.shape) > 2 else 1)

    metadata: dict[str, Any] = {
        "original_shape": {"width": original_width, "height": original_height},
        "filters": [],
    }
    artifacts: list[Artifact] = []

    LOGGER.debug("Applying grayscale conversion")
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    metadata["filters"].append("grayscale")

    LOGGER.debug("Applying CLAHE contrast enhancement")
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    equalized = clahe.apply(grayscale)
    metadata["filters"].append("clahe")

    LOGGER.debug("Applying bilateral denoising")
    denoised = cv2.bilateralFilter(equalized, d=9, sigmaColor=75, sigmaSpace=75)
    metadata["filters"].append("bilateral_denoise")

    LOGGER.debug("Applying adaptive threshold")
    thresholded = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        41,
        3,
    )
    metadata["filters"].append("adaptive_threshold")

    LOGGER.debug("Estimating and correcting skew")
    deskewed, applied_angle = _deskew(thresholded)
    metadata["deskew_angle"] = applied_angle
    residual_skew = _estimate_skew(deskewed)
    metadata["residual_skew"] = residual_skew
    
    if abs(applied_angle) > 0.1:
        LOGGER.info("Applied deskew correction: angle=%.2f degrees, residual_skew=%.2f", applied_angle, residual_skew)
    else:
        LOGGER.debug("No deskew needed: angle=%.2f degrees, residual_skew=%.2f", applied_angle, residual_skew)

    height = deskewed.shape[0]
    header_end = max(int(height * 0.2), 1)
    body_end = max(int(height * 0.85), header_end + 1)

    crops = {
        "full": deskewed,
        "header": deskewed[0:header_end, :],
        "body": deskewed[header_end:body_end, :],
        "totals": deskewed[body_end:, :] if body_end < height else deskewed[-max(height // 10, 1) :, :],
    }

    metadata["crops"] = {
        name: {"height": int(crop.shape[0]), "width": int(crop.shape[1])}
        for name, crop in crops.items()
    }
    
    LOGGER.debug(
        "Created crops: header=%dx%d, body=%dx%d, totals=%dx%d",
        metadata["crops"]["header"]["width"],
        metadata["crops"]["header"]["height"],
        metadata["crops"]["body"]["width"],
        metadata["crops"]["body"]["height"],
        metadata["crops"]["totals"]["width"],
        metadata["crops"]["totals"]["height"],
    )

    if save_intermediates:
        LOGGER.debug("Encoding intermediate artifacts")
        artifacts.extend(_encode_artifacts(crops))
        LOGGER.debug("Created %d artifacts", len(artifacts))

    LOGGER.debug("Preprocessing completed: filters=%s", ", ".join(metadata["filters"]))
    return PreprocessResult(processed_image=deskewed, crops=crops, metadata=metadata, artifacts=artifacts)


def _bytes_to_image(data: bytes) -> np.ndarray | None:
    buffer = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def _estimate_skew(image: np.ndarray) -> float:
    edges = cv2.Canny(image, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    if lines is None:
        return 0.0
    angles = []
    for rho, theta in lines[:, 0]:
        angle_deg = (theta * 180 / np.pi) - 90
        if -45 <= angle_deg <= 45:
            angles.append(angle_deg)
    if not angles:
        return 0.0
    return float(np.mean(angles))


def _deskew(image: np.ndarray) -> tuple[np.ndarray, float]:
    angle = _estimate_skew(image)
    if abs(angle) < 0.1:
        return image, 0.0
    height, width = image.shape[:2]
    center = (width // 2, height // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated, angle


def _encode_artifacts(crops: dict[str, np.ndarray]) -> list[Artifact]:
    artifacts: list[Artifact] = []
    for name, crop in crops.items():
        success, buffer = cv2.imencode(".tiff", crop)
        if not success:
            continue
        artifacts.append(
            Artifact(
                name=f"preprocessed/{name}.tiff",
                content=buffer.tobytes(),
                content_type="image/tiff",
                metadata={"shape": {"height": int(crop.shape[0]), "width": int(crop.shape[1])}},
            )
        )
    return artifacts

