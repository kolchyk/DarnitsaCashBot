from __future__ import annotations

from libs.common.config import AppSettings
from services.ocr_worker.postprocess import build_structured_payload, cluster_tokens_by_line
from services.ocr_worker.tesseract_runner import OcrToken


def _token(text: str, left: int, top: int, profile: str = "line_items", confidence: float = 0.9) -> OcrToken:
    return OcrToken(
        text=text,
        confidence=confidence,
        left=left,
        top=top,
        width=10,
        height=10,
        profile=profile,
    )


def test_cluster_tokens_by_line_groups_rows():
    tokens = [
        _token("A", left=0, top=0),
        _token("B", left=10, top=2),
        _token("C", left=0, top=30),
    ]
    clusters = cluster_tokens_by_line(tokens)
    assert len(clusters) == 2
    assert clusters[0].text == "A B"
    assert clusters[1].text == "C"


def test_build_structured_payload_extracts_entities():
    settings = AppSettings(telegram_bot_token="dummy", encryption_secret="secret")
    preprocess_metadata = {"crops": {"header": {"height": 30}}}
    tokens_by_profile = {
        "full": [
            _token("Pharma Market", left=0, top=5, profile="full"),
        ],
        "line_items": [
            _token("Citramon", left=0, top=60),
            _token("1", left=80, top=60),
            _token("x", left=90, top=60),
            _token("100,00", left=120, top=60),
        ],
        "totals": [
            _token("SUM", left=0, top=10, profile="totals"),
            _token("200,00", left=50, top=10, profile="totals"),
        ],
    }
    catalog_aliases = {"SKU-1": ["citramon"]}
    payload = build_structured_payload(
        preprocess_metadata=preprocess_metadata,
        tesseract_stats={},
        tokens_by_profile=tokens_by_profile,
        catalog_aliases=catalog_aliases,
        settings=settings,
    )

    assert payload["merchant"] == "PHARMA MARKET"
    assert payload["total"] == 20000
    assert payload["line_items"][0]["price"] == 10000
    assert payload["line_items"][0]["sku_code"] == "SKU-1"
    assert payload["manual_review_required"] is False
    assert payload["confidence"]["auto_accept_candidate"] is True

