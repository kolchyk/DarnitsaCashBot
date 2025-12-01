from __future__ import annotations

import cv2
import numpy as np

from services.ocr_worker.preprocess import preprocess_image


def test_preprocess_creates_expected_crops():
    image = np.full((200, 80, 3), 255, dtype=np.uint8)
    success, encoded = cv2.imencode(".png", image)
    assert success

    result = preprocess_image(encoded.tobytes(), save_intermediates=False)

    assert set(result.crops.keys()) == {"full", "header", "body", "totals"}
    assert result.metadata["crops"]["full"]["height"] == 200

