from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Any, Iterable, Sequence
import re
import unicodedata

import pendulum
from pendulum.parsing.exceptions import ParserError
from Levenshtein import distance as levenshtein_distance
from unidecode import unidecode

from libs.common import AppSettings

from .tesseract_runner import OcrToken

TOTAL_KEYWORDS = ("total", "итого", "всього", "sum", "сума", "amount")


@dataclass
class LineCluster:
    text: str
    tokens: list[OcrToken]

    @property
    def confidence(self) -> float:
        if not self.tokens:
            return 0.0
        return float(fmean(token.confidence for token in self.tokens))


def build_structured_payload(
    *,
    preprocess_metadata: dict[str, Any],
    tesseract_stats: dict[str, Any],
    tokens_by_profile: dict[str, list[OcrToken]],
    catalog_aliases: dict[str, list[str]],
    settings: AppSettings,
) -> dict[str, Any]:
    header_height = preprocess_metadata.get("crops", {}).get("header", {}).get("height", 0)
    merchant = _extract_merchant(tokens_by_profile.get("full", []), header_height)
    purchase_ts = _extract_purchase_ts(tokens_by_profile)

    line_clusters = cluster_tokens_by_line(tokens_by_profile.get("line_items", []))
    line_items = [_line_item_from_cluster(cluster, catalog_aliases) for cluster in line_clusters]

    total_candidates = cluster_tokens_by_line(tokens_by_profile.get("totals", []), y_threshold=25)
    total_amount = _detect_total(total_candidates)

    line_total_sum = sum(item["price"] for item in line_items if item["price"] is not None)
    anomalies: list[str] = []
    totals_tolerance = settings.ocr_totals_tolerance_percent
    if total_amount and line_total_sum:
        delta = abs(total_amount - line_total_sum)
        if total_amount > 0:
            delta_percent = delta / total_amount * 100
            if delta_percent > totals_tolerance:
                anomalies.append(f"totals_mismatch:{delta_percent:.2f}")

    line_confidences = [item["confidence"] for item in line_items if item["confidence"] is not None]
    mean_confidence = float(fmean(line_confidences)) if line_confidences else 0.0
    manual_review = (
        mean_confidence < settings.ocr_manual_review_threshold
        or (total_amount is None)
        or ("totals_mismatch" in "".join(anomalies))
    )
    auto_accept_candidate = (
        mean_confidence >= settings.ocr_auto_accept_threshold and not anomalies and not manual_review
    )

    payload = {
        "merchant": merchant,
        "purchase_ts": purchase_ts.isoformat() if purchase_ts else None,
        "total": total_amount,
        "line_items": [
            {
                "name": item["name"],
                "quantity": item["quantity"],
                "price": item["price"],
                "confidence": item["confidence"],
                "sku_code": item["sku_code"],
                "sku_match_score": item["sku_match_score"],
            }
            for item in line_items
        ],
        "confidence": {
            "mean": mean_confidence,
            "min": min(line_confidences) if line_confidences else 0.0,
            "max": max(line_confidences) if line_confidences else 0.0,
            "token_count": sum(len(cluster.tokens) for cluster in line_clusters),
            "auto_accept_candidate": auto_accept_candidate,
        },
        "preprocessing": preprocess_metadata,
        "tesseract_stats": tesseract_stats,
        "manual_review_required": manual_review,
        "anomalies": anomalies,
    }
    return payload


def cluster_tokens_by_line(tokens: Sequence[OcrToken], y_threshold: int = 18) -> list[LineCluster]:
    sorted_tokens = sorted(tokens, key=lambda token: token.top)
    clusters: list[list[OcrToken]] = []
    current_cluster: list[OcrToken] = []
    last_top = None

    for token in sorted_tokens:
        if not token.text:
            continue
        if last_top is None or abs(token.top - last_top) <= y_threshold:
            current_cluster.append(token)
        else:
            clusters.append(current_cluster)
            current_cluster = [token]
        last_top = token.top
    if current_cluster:
        clusters.append(current_cluster)

    return [
        LineCluster(text=_join_tokens(cluster), tokens=cluster)
        for cluster in clusters
        if _join_tokens(cluster)
    ]


def _join_tokens(tokens: Iterable[OcrToken]) -> str:
    return " ".join(token.text for token in sorted(tokens, key=lambda t: t.left))


def _extract_merchant(tokens: Sequence[OcrToken], header_height: int) -> str | None:
    header_tokens = [token for token in tokens if token.top <= header_height + 5]
    if not header_tokens:
        header_tokens = tokens
    clusters = cluster_tokens_by_line(header_tokens, y_threshold=12)
    if not clusters:
        return None
    candidate = clusters[0].text
    return _normalize_text(candidate)


def _extract_purchase_ts(tokens_by_profile: dict[str, list[OcrToken]]):
    combined_text = " ".join(token.text for token in tokens_by_profile.get("full", []))
    combined_text += " " + " ".join(token.text for token in tokens_by_profile.get("totals", []))
    combined_text = combined_text.strip()
    if not combined_text:
        return None

    date_patterns = [
        r"(?P<date>\d{2}[./-]\d{2}[./-]\d{4})\s+(?P<time>\d{2}:\d{2}(?::\d{2})?)",
        r"(?P<date>\d{4}-\d{2}-\d{2})[ T](?P<time>\d{2}:\d{2}(?::\d{2})?)",
        r"(?P<date>\d{2}[./-]\d{2}[./-]\d{4})",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, combined_text)
        if not match:
            continue
        date_part = match.group("date")
        time_part = match.groupdict().get("time")
        
        # Normalize date separators to dots for DD.MM.YYYY format
        normalized_date = date_part.replace("/", ".").replace("-", ".")
        
        # Try parsing with time component
        if time_part:
            # Determine time format based on whether seconds are present
            time_format = "HH:mm:ss" if ":" in time_part and time_part.count(":") == 2 else "HH:mm"
            
            # Try multiple date formats with normalized separators
            date_time_formats = [
                (f"{normalized_date} {time_part}", f"DD.MM.YYYY {time_format}"),
                (f"{date_part} {time_part}", f"DD.MM.YYYY {time_format}"),  # Original separators
                (f"{date_part} {time_part}", None),  # Let pendulum.parse handle it
            ]
            
            for date_time_str, fmt in date_time_formats:
                try:
                    if fmt:
                        return pendulum.from_format(date_time_str, fmt)
                    else:
                        return pendulum.parse(date_time_str, strict=False)
                except (ParserError, ValueError):
                    continue
        
        # Try parsing date only
        date_formats = [
            (normalized_date, "DD.MM.YYYY"),
            (date_part, None),  # Let pendulum.parse handle it
        ]
        
        for date_str, fmt in date_formats:
            try:
                if fmt:
                    return pendulum.from_format(date_str, fmt)
                else:
                    return pendulum.parse(date_str, strict=False)
            except (ParserError, ValueError):
                continue
    
    return None


def _line_item_from_cluster(cluster: LineCluster, catalog_aliases: dict[str, list[str]]) -> dict[str, Any]:
    normalized_name = _normalize_text(cluster.text)
    quantity, price = _extract_quantity_and_price(normalized_name)
    sku_code, score = _match_sku(normalized_name, catalog_aliases)

    return {
        "name": normalized_name,
        "quantity": quantity,
        "price": price,
        "confidence": cluster.confidence,
        "sku_code": sku_code,
        "sku_match_score": score,
    }


def _extract_quantity_and_price(text: str) -> tuple[int, int | None]:
    qty = 1
    price = None
    multiplier_pattern = re.search(r"(?P<qty>\d+)\s*[xх×]\s*(?P<price>\d+[.,]?\d*)", text.lower())
    if multiplier_pattern:
        qty = int(multiplier_pattern.group("qty"))
        price = _to_minor_units(multiplier_pattern.group("price"))
        return qty, price

    numeric_candidates = re.findall(r"\d+[.,]?\d*", text)
    if numeric_candidates:
        price = _to_minor_units(numeric_candidates[-1])
    return qty, price


def _detect_total(clusters: Sequence[LineCluster]) -> int | None:
    for cluster in clusters:
        normalized = _normalize_text(cluster.text).lower()
        if any(keyword in normalized for keyword in TOTAL_KEYWORDS):
            numbers = re.findall(r"\d+[.,]?\d*", normalized)
            if numbers:
                return _to_minor_units(numbers[-1])
    # fallback to largest number
    best = None
    for cluster in clusters:
        numbers = re.findall(r"\d+[.,]?\d*", cluster.text)
        for number in numbers:
            candidate = _to_minor_units(number)
            if best is None or (candidate and candidate > best):
                best = candidate
    return best


def _match_sku(name: str, catalog_aliases: dict[str, list[str]]) -> tuple[str | None, float]:
    best_score = 0.0
    best_code: str | None = None
    normalized = name.lower()
    for sku_code, aliases in catalog_aliases.items():
        for alias in aliases:
            similarity = _similarity(normalized, alias.lower())
            if similarity > best_score:
                best_score = similarity
                best_code = sku_code
    if best_score < 0.75:
        return None, best_score
    return best_code, best_score


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 0.0
    distance = levenshtein_distance(a, b)
    return 1 - (distance / max_len)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("₴", " грн ")
    normalized = unidecode(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.upper()


def _to_minor_units(value: str) -> int:
    cleaned = value.replace(" ", "").replace(",", ".")
    try:
        amount = float(cleaned)
    except ValueError:
        return 0
    return int(round(amount * 100))

