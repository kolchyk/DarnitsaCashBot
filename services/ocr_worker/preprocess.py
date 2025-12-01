from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


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
    image = _bytes_to_image(image_bytes)
    if image is None:
        raise UnreadableImageError("Failed to decode receipt image")

    metadata: dict[str, Any] = {
        "original_shape": {"width": int(image.shape[1]), "height": int(image.shape[0])},
        "filters": [],
    }
    artifacts: list[Artifact] = []

    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    metadata["filters"].append("grayscale")

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    equalized = clahe.apply(grayscale)
    metadata["filters"].append("clahe")

    denoised = cv2.bilateralFilter(equalized, d=9, sigmaColor=75, sigmaSpace=75)
    metadata["filters"].append("bilateral_denoise")

    thresholded = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        41,
        3,
    )
    metadata["filters"].append("adaptive_threshold")

    deskewed, applied_angle = _deskew(thresholded)
    metadata["deskew_angle"] = applied_angle
    metadata["residual_skew"] = _estimate_skew(deskewed)

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

    if save_intermediates:
        artifacts.extend(_encode_artifacts(crops))

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

