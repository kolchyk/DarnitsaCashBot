from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from datetime import datetime
from typing import Any
from uuid import UUID

from Levenshtein import distance as levenshtein_distance
from unidecode import unidecode

from libs.common import get_settings
from libs.common.darnitsa import has_darnitsa_prefix
from libs.common.storage import StorageClient
from libs.data import async_session_factory
from libs.data.models import Receipt, ReceiptStatus
from libs.data.repositories import CatalogRepository

from .qr_scanner import QRCodeNotFoundError, detect_qr_code
from .receipt_scraper import ScrapingError, scrape_receipt_data
from .preprocess import preprocess_image, UnreadableImageError
from .tesseract_runner import TesseractRunner, TesseractRuntimeError
from .postprocess import build_structured_payload

LOGGER = logging.getLogger(__name__)


async def process_message(payload: dict) -> None:
    settings = get_settings()
    receipt_id = UUID(payload["receipt_id"])
    storage_key = payload.get("storage_key", "unknown")
    
    LOGGER.info(
        "Starting QR code processing for receipt %s, storage_key=%s",
        receipt_id,
        storage_key,
    )
    
    async with async_session_factory() as session:
        receipt: Receipt | None = await session.get(Receipt, receipt_id)
        if not receipt:
            LOGGER.warning("Receipt %s not found in database", receipt_id)
            return
        storage = StorageClient(settings)
        image_bytes = await storage.download(storage_key)
        LOGGER.info("Downloaded receipt image: %d bytes", len(image_bytes))

        try:
            # Step 1: Detect QR code
            LOGGER.debug("Starting QR code detection for receipt %s", receipt_id)
            qr_url = await asyncio.to_thread(detect_qr_code, image_bytes)
            
            if not qr_url:
                raise QRCodeNotFoundError("QR code not found in receipt image")
            
            LOGGER.info("QR code detected for receipt %s: url=%s", receipt_id, qr_url)
            
            # Step 2: Try to scrape receipt data from URL
            LOGGER.debug("Starting receipt scraping for receipt %s", receipt_id)
            scraped_data = None
            try:
                scraped_data = await asyncio.to_thread(scrape_receipt_data, qr_url)
                items_count = len(scraped_data.get("line_items", []))
                LOGGER.info(
                    "Scraping completed for receipt %s: merchant=%s, line_items=%d, total=%s",
                    receipt_id,
                    scraped_data.get("merchant"),
                    items_count,
                    scraped_data.get("total"),
                )
                
                # If scraping didn't find items, fallback to OCR
                if items_count == 0:
                    LOGGER.warning(
                        "Scraping found 0 items for receipt %s, falling back to OCR",
                        receipt_id,
                    )
                    scraped_data = None
            except ScrapingError as exc:
                LOGGER.warning(
                    "Scraping failed for receipt %s: %s, falling back to OCR",
                    receipt_id,
                    exc,
                )
                scraped_data = None
            
            # Step 2b: Fallback to OCR if scraping failed or found no items
            if scraped_data is None:
                LOGGER.info("Using OCR fallback for receipt %s", receipt_id)
                scraped_data = await _process_with_ocr(image_bytes, settings, session)
            
        except QRCodeNotFoundError as exc:
            LOGGER.warning("QR code not found for receipt %s: %s", receipt_id, exc, exc_info=True)
            receipt.status = ReceiptStatus.REJECTED
            failure_payload = {"error": str(exc), "type": "qr_code_not_found"}
            receipt.ocr_payload = failure_payload
            await session.commit()
            await _publish_failure(payload, failure_payload)
            return
        except Exception as exc:
            LOGGER.error("Unexpected error processing receipt %s: %s", receipt_id, exc, exc_info=True)
            receipt.status = ReceiptStatus.REJECTED
            failure_payload = {"error": f"Unexpected error: {str(exc)}", "type": "processing_error"}
            receipt.ocr_payload = failure_payload
            await session.commit()
            await _publish_failure(payload, failure_payload)
            return

        # Step 3: Load catalog and enrich line items with SKU matching
        catalog_repo = CatalogRepository(session)
        catalog = await catalog_repo.list_active()
        catalog_aliases = {
            item.sku_code: [alias.lower() for alias in item.product_aliases] for item in catalog
        }
        LOGGER.info(
            "Loaded catalog for receipt %s: active_items=%d, total_aliases=%d",
            receipt_id,
            len(catalog),
            sum(len(aliases) for aliases in catalog_aliases.values()),
        )

        # Enrich scraped line items with SKU matching and Darnitsa detection
        LOGGER.debug("Enriching line items with SKU matching for receipt %s", receipt_id)
        enriched_line_items = []
        for item in scraped_data.get("line_items", []):
            enriched_item = _enrich_line_item(item, catalog_aliases)
            enriched_line_items.append(enriched_item)
        
        scraped_data["line_items"] = enriched_line_items
        
        # Log enriched line items
        if enriched_line_items:
            LOGGER.debug("Enriched line items for receipt %s:", receipt_id)
            for idx, item in enumerate(enriched_line_items, 1):
                sku_info = f", sku={item.get('sku_code')}" if item.get("sku_code") else ""
                sku_score = f", sku_score={item.get('sku_match_score', 0):.3f}" if item.get("sku_match_score") else ""
                darnitsa_info = ", is_darnitsa=True" if item.get("is_darnitsa") else ""
                LOGGER.debug(
                    "  Item %d: name='%s', quantity=%d, price=%s%s%s%s",
                    idx,
                    item.get("name", "")[:50],
                    item.get("quantity", 0),
                    item.get("price"),
                    sku_info,
                    sku_score,
                    darnitsa_info,
                )

        receipt.ocr_payload = scraped_data
        if scraped_data.get("merchant"):
            receipt.merchant = scraped_data["merchant"]
        purchase_ts = scraped_data.get("purchase_ts")
        if purchase_ts:
            receipt.purchase_ts = datetime.fromisoformat(purchase_ts)
        receipt.status = ReceiptStatus.PROCESSING
        await session.commit()
        
        LOGGER.info(
            "QR code processing completed for receipt %s: status=%s, merchant=%s, line_items=%d, total=%s",
            receipt_id,
            receipt.status,
            receipt.merchant,
            len(enriched_line_items),
            scraped_data.get("total"),
        )
        
        structured_payload = scraped_data

    # Trigger rules engine evaluation after QR code processing completes successfully
    LOGGER.debug("Triggering rules engine evaluation for receipt %s", receipt_id)
    try:
        from apps.api_gateway.services.rules.service import evaluate
        await evaluate({
            "receipt_id": str(receipt_id),
            "ocr_payload": structured_payload,
        })
        LOGGER.debug("Rules engine evaluation completed for receipt %s", receipt_id)
    except Exception as e:
        LOGGER.error(
            "Failed to evaluate receipt %s in rules engine: %s: %s",
            receipt_id,
            type(e).__name__,
            str(e),
            exc_info=True,
        )


def _enrich_line_item(item: dict[str, Any], catalog_aliases: dict[str, list[str]]) -> dict[str, Any]:
    """Enrich a scraped line item with SKU matching and Darnitsa detection."""
    original_name = item.get("name", "")
    normalized_name = _normalize_text(original_name)
    
    # SKU matching
    sku_code, sku_score = _match_sku(normalized_name, catalog_aliases)
    
    # Darnitsa detection
    is_darnitsa = has_darnitsa_prefix(original_name) or has_darnitsa_prefix(normalized_name)
    
    enriched = {
        "name": original_name,
        "original_name": original_name,
        "normalized_name": normalized_name,
        "quantity": item.get("quantity", 1),
        "price": item.get("price"),
        "confidence": item.get("confidence", 1.0),
        "sku_code": sku_code,
        "sku_match_score": sku_score,
        "is_darnitsa": is_darnitsa,
    }
    
    return enriched


def _normalize_text(text: str) -> str:
    """Normalize text for SKU matching (same as postprocess.py)."""
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("₴", " грн ")
    normalized = unidecode(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.upper()


def _match_sku(name: str, catalog_aliases: dict[str, list[str]]) -> tuple[str | None, float]:
    """Match product name to SKU code using catalog aliases."""
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
    """Calculate similarity between two strings using Levenshtein distance."""
    if not a or not b:
        return 0.0
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 0.0
    distance = levenshtein_distance(a, b)
    return 1 - (distance / max_len)


async def _process_with_ocr(
    image_bytes: bytes,
    settings: Any,
    session: Any,
) -> dict[str, Any]:
    """Process receipt image using OCR as fallback when scraping fails."""
    LOGGER.info("Processing receipt with OCR")
    
    # Step 1: Preprocess image
    preprocess_result = await asyncio.to_thread(preprocess_image, image_bytes, save_intermediates=False)
    
    # Step 2: Run Tesseract OCR
    runner = TesseractRunner(settings)
    tesseract_result = await asyncio.to_thread(runner.run, preprocess_result)
    
    # Step 3: Load catalog for SKU matching
    from libs.data.repositories import CatalogRepository
    catalog_repo = CatalogRepository(session)
    catalog = await catalog_repo.list_active()
    catalog_aliases = {
        item.sku_code: [alias.lower() for alias in item.product_aliases] for item in catalog
    }
    
    # Step 4: Build structured payload
    structured_payload = build_structured_payload(
        preprocess_metadata=preprocess_result.metadata,
        tesseract_stats=tesseract_result.stats,
        tokens_by_profile=tesseract_result.tokens_by_profile,
        catalog_aliases=catalog_aliases,
        settings=settings,
    )
    
    LOGGER.info(
        "OCR processing completed: merchant=%s, line_items=%d, total=%s",
        structured_payload.get("merchant"),
        len(structured_payload.get("line_items", [])),
        structured_payload.get("total"),
    )
    
    return structured_payload


async def _publish_failure(payload: dict, failure_payload: dict) -> None:
    # RabbitMQ removed - failures are now stored in database only
    pass

