from io import BytesIO
from pathlib import Path
import sys

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.append(str(PROJECT_ROOT))

from apps.api_gateway.services.ocr import qr_scanner
from apps.api_gateway.services.ocr.qr_scanner import QRCodeNotFoundError, detect_qr_code


def _blank_image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (10, 10), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_detect_qr_code_returns_data_when_decoder_finds_qr(monkeypatch):
    decoded_data = b"https://example.com"

    class DummyDecoded:
        type = "QRCODE"
        data = decoded_data

    def fake_decode(_image):
        return [DummyDecoded()]

    monkeypatch.setattr(qr_scanner, "_get_decoder", lambda: fake_decode)

    assert detect_qr_code(_blank_image_bytes()) == decoded_data.decode("utf-8")


def test_detect_qr_code_ignores_non_qr_results(monkeypatch):
    class DummyDecoded:
        type = "CODE128"
        data = b"should-not-be-used"

    monkeypatch.setattr(qr_scanner, "_get_decoder", lambda: lambda _image: [DummyDecoded()])

    assert detect_qr_code(_blank_image_bytes()) is None


def test_detect_qr_code_raises_if_decoder_missing(monkeypatch):
    def raise_missing():
        raise QRCodeNotFoundError("decoder missing")

    monkeypatch.setattr(qr_scanner, "_get_decoder", raise_missing)

    with pytest.raises(QRCodeNotFoundError):
        detect_qr_code(_blank_image_bytes())
