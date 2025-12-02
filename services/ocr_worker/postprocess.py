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

import logging

from libs.common import AppSettings
from libs.common.constants import DARNITSA_KEYWORDS_CYRILLIC, DARNITSA_KEYWORDS_LATIN

from .tesseract_runner import OcrToken

LOGGER = logging.getLogger(__name__)

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
    LOGGER.debug("Extracted merchant: %s", merchant)
    
    purchase_ts = _extract_purchase_ts(tokens_by_profile)
    LOGGER.debug("Extracted purchase timestamp: %s", purchase_ts.isoformat() if purchase_ts else None)

    line_tokens = tokens_by_profile.get("line_items", [])
    LOGGER.debug("Clustering %d line item tokens", len(line_tokens))
    line_clusters = cluster_tokens_by_line(line_tokens)
    LOGGER.debug("Created %d line clusters from tokens", len(line_clusters))
    
    line_items = []
    sku_matches = 0
    for cluster in line_clusters:
        item = _line_item_from_cluster(cluster, catalog_aliases)
        # Filter out merchant name from line items
        if _is_merchant_name(item, merchant):
            LOGGER.debug("Filtering out merchant name from line items: '%s'", item.get("name", "")[:50])
            continue
        line_items.append(item)
        if item.get("sku_code"):
            sku_matches += 1
    
    LOGGER.debug("Processed %d line items, %d SKU matches found", len(line_items), sku_matches)

    total_tokens = tokens_by_profile.get("totals", [])
    LOGGER.debug("Processing %d total tokens", len(total_tokens))
    total_candidates = cluster_tokens_by_line(total_tokens, y_threshold=25)
    
    # If totals profile didn't find enough tokens, also search in full tokens
    # (totals might be in the full profile if cropping didn't work well)
    if len(total_candidates) == 0 or (len(total_candidates) == 1 and total_candidates[0].confidence == 0.0):
        LOGGER.debug("Totals profile had insufficient tokens, searching in full tokens")
        full_tokens = tokens_by_profile.get("full", [])
        if full_tokens:
            # Get tokens from bottom 15% of receipt (where totals usually are)
            max_y = max(token.top for token in full_tokens) if full_tokens else 0
            bottom_threshold = max_y * 0.85
            bottom_tokens = [token for token in full_tokens if token.top >= bottom_threshold]
            if bottom_tokens:
                bottom_candidates = cluster_tokens_by_line(bottom_tokens, y_threshold=25)
                LOGGER.debug("Found %d candidates in bottom section of full tokens", len(bottom_candidates))
                total_candidates.extend(bottom_candidates)
    
    total_amount = _detect_total(total_candidates)
    LOGGER.debug("Detected total amount: %s from %d candidates", total_amount, len(total_candidates))

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
                "original_name": item.get("original_name", item["name"]),  # Оригинальный текст
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

    line_clusters = [
        LineCluster(text=_join_tokens(cluster), tokens=cluster)
        for cluster in clusters
        if _join_tokens(cluster)
    ]
    
    LOGGER.debug(
        "Clustered %d tokens into %d lines (y_threshold=%d)",
        len(sorted_tokens),
        len(line_clusters),
        y_threshold,
    )
    
    return line_clusters


def _join_tokens(tokens: Iterable[OcrToken]) -> str:
    return " ".join(token.text for token in sorted(tokens, key=lambda t: t.left))


def _extract_merchant(tokens: Sequence[OcrToken], header_height: int) -> str | None:
    """Extract merchant name from OCR tokens, prioritizing Darnitsa detection."""
    if not tokens:
        return None
    
    # Calculate header boundary - use first 20% of receipt height
    max_header_y = header_height if header_height > 0 else max(token.top for token in tokens) // 5
    
    # Get header tokens only (first 20% of receipt)
    header_tokens = [token for token in tokens if token.top <= max_header_y]
    if not header_tokens:
        # If no header tokens found, use first 30% as fallback
        max_y = max(token.top for token in tokens) if tokens else 0
        header_tokens = [token for token in tokens if token.top <= max_y * 0.3]
    
    if not header_tokens:
        return None
    
    clusters = cluster_tokens_by_line(header_tokens, y_threshold=12)
    if not clusters:
        return None
    
    # Helper function to check if a cluster looks like a product name (not merchant)
    def _is_product_like(cluster: LineCluster) -> bool:
        """Check if cluster looks like a product name rather than merchant name."""
        text = cluster.text.lower()
        # Product names typically contain:
        # - Numbers followed by units (mg, мл, табл, etc.)
        # - Price patterns (numbers with decimal points)
        # - Quantity patterns (x, ×, шт)
        product_patterns = [
            r'\d+\s*(мг|мл|табл|шт|гр|кг|л)',  # Numbers with units
            r'\d+[.,]\d+\s*(грн|₴|uah)',  # Price patterns
            r'\d+\s*[xх×]\s*\d+',  # Quantity patterns
            r'№\s*\d+',  # Product codes
        ]
        for pattern in product_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    # Search for Darnitsa keywords in header clusters first (excluding product-like clusters)
    for cluster in clusters:
        if _is_product_like(cluster):
            LOGGER.debug("Skipping product-like cluster for merchant: '%s'", cluster.text[:50])
            continue
            
        # Normalize Unicode (NFC) before lowercasing to ensure consistent matching
        # This matches the normalization used in rules_engine/service.py
        text_normalized = unicodedata.normalize("NFC", cluster.text).lower()
        normalized_text = _normalize_text(cluster.text).lower()
        
        # Normalize keywords for consistent comparison (same as rules_engine)
        cyrillic_keywords_normalized = [unicodedata.normalize("NFC", kw).lower() for kw in DARNITSA_KEYWORDS_CYRILLIC]
        latin_keywords_normalized = [kw.lower() for kw in DARNITSA_KEYWORDS_LATIN]
        
        # Check for Darnitsa in original text (Cyrillic) - use normalized comparison
        matched_keyword = None
        for i, keyword_normalized in enumerate(cyrillic_keywords_normalized):
            if keyword_normalized in text_normalized:
                matched_keyword = DARNITSA_KEYWORDS_CYRILLIC[i]
                LOGGER.debug("Found Darnitsa merchant (cyrillic) '%s' in header: '%s'", matched_keyword, cluster.text[:50])
                return cluster.text.strip()
        
        # Check for Darnitsa in normalized text (transliteration)
        for i, keyword_normalized in enumerate(latin_keywords_normalized):
            if keyword_normalized in normalized_text:
                matched_keyword = DARNITSA_KEYWORDS_LATIN[i]
                LOGGER.debug("Found Darnitsa merchant (latin) '%s' in header: '%s'", matched_keyword, cluster.text[:50])
                return cluster.text.strip()
    
    # If Darnitsa not found, return first non-product-like header cluster
    for cluster in clusters:
        if not _is_product_like(cluster):
            LOGGER.debug("Using first non-product header cluster as merchant: '%s'", cluster.text[:50])
            return cluster.text.strip()
    
    # Last resort: return first header cluster
    if clusters:
        LOGGER.debug("Fallback: using first header cluster as merchant: '%s'", clusters[0].text[:50])
        return clusters[0].text.strip()
    
    return None


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


def _is_merchant_name(item: dict[str, Any], merchant: str | None) -> bool:
    """Check if a line item is actually the merchant name (not a product)."""
    if not merchant:
        return False
    
    item_name = item.get("original_name") or item.get("name", "")
    if not item_name:
        return False
    
    # Normalize both for comparison
    item_normalized = _normalize_text(item_name).lower()
    merchant_normalized = _normalize_text(merchant).lower()
    
    # Check if item name matches merchant name (allowing for partial matches)
    # If item is very similar to merchant name, it's likely the merchant name
    if merchant_normalized in item_normalized or item_normalized in merchant_normalized:
        # But only filter if it doesn't have product-like patterns
        # (if it has prices, quantities, etc., it might be a product with merchant name)
        if not _has_product_patterns(item_name):
            LOGGER.debug("Item matches merchant name and has no product patterns: '%s'", item_name[:50])
            return True
    
    # Also check if item only contains Darnitsa keywords without product patterns
    # Normalize Unicode (NFC) before lowercasing to ensure consistent matching
    item_normalized = unicodedata.normalize("NFC", item_name).lower()
    normalized_item = _normalize_text(item_name).lower()
    
    # Normalize keywords for consistent comparison (same as rules_engine)
    cyrillic_keywords_normalized = [unicodedata.normalize("NFC", kw).lower() for kw in DARNITSA_KEYWORDS_CYRILLIC]
    latin_keywords_normalized = [kw.lower() for kw in DARNITSA_KEYWORDS_LATIN]
    
    # Check for Darnitsa keywords - use normalized comparison
    has_darnitsa_keyword = (
        any(keyword_normalized in item_normalized for keyword_normalized in cyrillic_keywords_normalized) or
        any(keyword_normalized in normalized_item for keyword_normalized in latin_keywords_normalized)
    )
    
    # If it has Darnitsa keyword but no product patterns and no price/quantity, it's likely merchant name
    if has_darnitsa_keyword and not _has_product_patterns(item_name):
        # Check if it has no meaningful price or quantity
        price = item.get("price")
        quantity = item.get("quantity", 1)
        if (price is None or price == 0) and quantity == 1:
            LOGGER.debug("Item contains Darnitsa keyword but no product patterns: '%s'", item_name[:50])
            return True
    
    return False


def _has_product_patterns(text: str) -> bool:
    """Check if text contains product-like patterns (numbers, prices, quantities, units)."""
    text_lower = text.lower()
    # Product patterns:
    # - Numbers followed by units (mg, мл, табл, etc.)
    # - Price patterns (numbers with decimal points, currency symbols)
    # - Quantity patterns (x, ×, шт)
    # - Product codes (№, codes)
    product_patterns = [
        r'\d+\s*(мг|мл|табл|шт|гр|кг|л|mg|ml|tab|pcs)',  # Numbers with units
        r'\d+[.,]\d+\s*(грн|₴|uah|usd|eur)',  # Price patterns
        r'\d+\s*[xх×]\s*\d+',  # Quantity patterns
        r'№\s*\d+',  # Product codes
        r'\d+\s*шт',  # Quantity in Ukrainian
        r'x\s*\d+',  # Quantity pattern
    ]
    for pattern in product_patterns:
        if re.search(pattern, text_lower):
            return True
    return False


def _line_item_from_cluster(cluster: LineCluster, catalog_aliases: dict[str, list[str]]) -> dict[str, Any]:
    original_name = cluster.text.strip()  # Оригинальный текст (сохраняем как основной)
    normalized_name = _normalize_text(original_name)  # Нормализованный текст только для поиска SKU
    quantity, price = _extract_quantity_and_price(normalized_name)
    sku_code, score = _match_sku(normalized_name, catalog_aliases)

    return {
        "name": original_name,  # Используем оригинальный текст как основной
        "original_name": original_name,  # Оригинальный текст для поиска кириллицы
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
    """Detect total amount from clusters, prioritizing lines with total keywords."""
    if not clusters:
        return None
    
    # First pass: look for clusters containing total keywords
    for cluster in clusters:
        normalized = _normalize_text(cluster.text).lower()
        if any(keyword in normalized for keyword in TOTAL_KEYWORDS):
            # Extract numbers from this cluster
            numbers = re.findall(r"\d+[.,]?\d*", cluster.text)
            if numbers:
                # Use the last (largest) number in the cluster
                total = _to_minor_units(numbers[-1])
                if total and total > 0:
                    LOGGER.debug("Found total via keyword match: '%s' -> %d", cluster.text[:50], total)
                    return total
    
    # Second pass: look for the largest number in clusters (fallback)
    # Prioritize clusters with higher confidence
    best = None
    best_confidence = 0.0
    
    for cluster in clusters:
        numbers = re.findall(r"\d+[.,]?\d*", cluster.text)
        for number in numbers:
            candidate = _to_minor_units(number)
            # Prefer larger numbers and higher confidence clusters
            if candidate and candidate > 0:
                if best is None or (candidate > best) or (candidate == best and cluster.confidence > best_confidence):
                    best = candidate
                    best_confidence = cluster.confidence
    
    if best:
        LOGGER.debug("Found total via largest number: %d (confidence=%.3f)", best, best_confidence)
    
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
    
    if best_score >= 0.75:
        LOGGER.debug("SKU match found: name='%s' -> sku=%s, score=%.3f", name[:50], best_code, best_score)
    else:
        LOGGER.debug("No SKU match: name='%s', best_score=%.3f (threshold=0.75)", name[:50], best_score)
    
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

