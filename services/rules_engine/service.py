from __future__ import annotations

import asyncio
import json
import logging
import unicodedata
from datetime import datetime, timedelta, timezone
from uuid import UUID

from unidecode import unidecode

from libs.common import configure_logging, get_settings
from libs.common.analytics import AnalyticsClient
from libs.common.constants import (
    DARNITSA_KEYWORDS_CYRILLIC,
    DARNITSA_KEYWORDS_LATIN,
    ELIGIBILITY_WINDOW_DAYS,
    MAX_RECEIPTS_PER_DAY,
)
from libs.common.crypto import Encryptor
from libs.common.events import EVENT_RECEIPT_ACCEPTED, Event, get_event_bus
from libs.common.portmone import PortmoneDirectClient
from libs.data import async_session_factory
from libs.data.models import LineItem, Receipt
from libs.data.repositories import ReceiptRepository

LOGGER = logging.getLogger(__name__)


def _normalize_for_matching(text: str) -> str:
    """Normalize text for keyword matching: NFC normalization + lowercase."""
    return unicodedata.normalize("NFC", text).lower()


async def evaluate(payload: dict) -> None:
    receipt_id = UUID(payload["receipt_id"])
    async with async_session_factory() as session:
        receipt: Receipt | None = await session.get(Receipt, receipt_id)
        if not receipt:
            return
        ocr_payload = payload.get("ocr_payload") or {}
        
        # Check if this is an OCR error
        if ocr_payload.get("error") or payload.get("status") == "failed":
            receipt.status = "rejected"
            await session.commit()
            return

        repo = ReceiptRepository(session)
        daily_count = await repo.daily_submission_count(receipt.user_id)
        if daily_count > MAX_RECEIPTS_PER_DAY:
            receipt.status = "rejected"
            await session.commit()
            return

        purchase_ts = ocr_payload.get("purchase_ts")
        if purchase_ts:
            receipt.purchase_ts = datetime.fromisoformat(purchase_ts)
            if receipt.purchase_ts < datetime.now(timezone.utc) - timedelta(days=ELIGIBILITY_WINDOW_DAYS):
                receipt.status = "rejected"
                await session.commit()
                return

        # Accept all receipts that successfully passed OCR
        # Recognize and save all products from the receipt
        line_items = ocr_payload.get("line_items", [])
        
        # Check that OCR successfully recognized at least one product
        has_items = len(line_items) > 0
        
        # Check for "Дарниця" in product names and merchant name
        # Use case-insensitive search
        # Include different cases and spelling variants in Ukrainian
        has_darnitsa = False
        
        # First, check merchant name for Darnitsa keywords
        if receipt.merchant:
            # Normalize merchant name for matching (NFC + lowercase)
            merchant_normalized = _normalize_for_matching(receipt.merchant)
            # Also create transliterated version for Latin keyword matching
            merchant_transliterated = unidecode(merchant_normalized)
            
            # Normalize keywords for consistent comparison
            cyrillic_keywords_normalized = [_normalize_for_matching(kw) for kw in DARNITSA_KEYWORDS_CYRILLIC]
            latin_keywords_normalized = [kw.lower() for kw in DARNITSA_KEYWORDS_LATIN]
            
            # Check for Darnitsa in merchant name (Cyrillic)
            matched_keyword = None
            for i, keyword_normalized in enumerate(cyrillic_keywords_normalized):
                if keyword_normalized in merchant_normalized:
                    matched_keyword = DARNITSA_KEYWORDS_CYRILLIC[i]
                    has_darnitsa = True
                    LOGGER.info("Found Darnitsa keyword (cyrillic) '%s' in merchant: '%s'", matched_keyword, receipt.merchant[:50])
                    break
            # Check in transliterated merchant name (Latin)
            if not has_darnitsa:
                for i, keyword_normalized in enumerate(latin_keywords_normalized):
                    if keyword_normalized in merchant_transliterated:
                        matched_keyword = DARNITSA_KEYWORDS_LATIN[i]
                        has_darnitsa = True
                        LOGGER.info("Found Darnitsa keyword (latin) '%s' in merchant: '%s'", matched_keyword, receipt.merchant[:50])
                        break
            if not has_darnitsa:
                LOGGER.info("No Darnitsa keyword found in merchant '%s' (normalized: '%s', transliterated: '%s', checked %d cyrillic + %d latin keywords)", 
                           receipt.merchant[:50], merchant_normalized[:50], merchant_transliterated[:50], 
                           len(DARNITSA_KEYWORDS_CYRILLIC), len(DARNITSA_KEYWORDS_LATIN))
                LOGGER.debug("Cyrillic keywords checked: %s", DARNITSA_KEYWORDS_CYRILLIC)
                LOGGER.debug("Latin keywords checked: %s", DARNITSA_KEYWORDS_LATIN)
        
        # Save all recognized products and check for Darnitsa
        LOGGER.info(
            "Evaluating receipt %s: line_items=%d, daily_count=%d/%d, merchant=%s, has_darnitsa_so_far=%s",
            receipt_id,
            len(line_items),
            daily_count,
            MAX_RECEIPTS_PER_DAY,
            receipt.merchant[:50] if receipt.merchant else "None",
            has_darnitsa,
        )
        
        # Normalize keywords once for consistent comparison
        cyrillic_keywords_normalized = [_normalize_for_matching(kw) for kw in DARNITSA_KEYWORDS_CYRILLIC]
        latin_keywords_normalized = [kw.lower() for kw in DARNITSA_KEYWORDS_LATIN]
        
        # Log all item names for debugging if Darnitsa not found in merchant
        if not has_darnitsa and line_items:
            LOGGER.debug("Checking %d line items for Darnitsa keywords. Item names:", len(line_items))
            for idx, item in enumerate(line_items[:10]):  # Log first 10 items
                item_name = item.get("original_name") or item.get("name", "")
                LOGGER.debug("  Item %d: '%s'", idx + 1, item_name[:100])
        
        for item in line_items:
            # Get original text - check both 'name' and 'original_name' fields
            original_name = item.get("original_name") or item.get("name", "")
            if not original_name:
                LOGGER.debug("Skipping item with empty name: %s", item)
                continue
            
            # Normalize for matching (NFC + lowercase)
            item_normalized = _normalize_for_matching(original_name)
            # Also create transliterated version for Latin keyword matching
            item_transliterated = unidecode(item_normalized)
            
            # Check for Darnitsa in original text (Cyrillic) - use normalized comparison
            matched_keyword = None
            for i, keyword_normalized in enumerate(cyrillic_keywords_normalized):
                if keyword_normalized in item_normalized:
                    matched_keyword = DARNITSA_KEYWORDS_CYRILLIC[i]
                    has_darnitsa = True
                    LOGGER.info("Found Darnitsa keyword (cyrillic) '%s' in item: '%s' (normalized: '%s')", 
                              matched_keyword, original_name[:100], item_normalized[:100])
                    break
            # Check in transliterated text (Latin) - only if not already found
            if not has_darnitsa:
                for i, keyword_normalized in enumerate(latin_keywords_normalized):
                    if keyword_normalized in item_transliterated:
                        matched_keyword = DARNITSA_KEYWORDS_LATIN[i]
                        has_darnitsa = True
                        LOGGER.info("Found Darnitsa keyword (latin) '%s' in item: '%s' (transliterated: '%s')", 
                                  matched_keyword, original_name[:100], item_transliterated[:100])
                        break
            
            # Log items that don't match for debugging (only if Darnitsa not found yet)
            if not has_darnitsa and LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug("Item does not contain Darnitsa: '%s' (normalized: '%s', transliterated: '%s')", 
                           original_name[:100], item_normalized[:100], item_transliterated[:100])
            
            quantity = int(item.get("quantity", 1))
            price = item.get("price")
            if price is None:
                price = 0
            else:
                price = int(price)
                # Validate price: cap at 1 million UAH (100 million kopecks) to prevent
                # obviously wrong values like phone numbers being saved as prices
                MAX_REASONABLE_PRICE_KOPECKS = 100_000_000  # 1 million UAH
                if price > MAX_REASONABLE_PRICE_KOPECKS:
                    LOGGER.warning(
                        "Price %d kopecks exceeds reasonable maximum for item '%s', capping to 0",
                        price,
                        original_name[:50],
                    )
                    price = 0
            confidence = float(item.get("confidence", 0))
            sku_code = item.get("sku_code")  # Use SKU from OCR if available
            
            session.add(
                LineItem(
                    receipt_id=receipt.id,
                    sku_code=sku_code,
                    product_name=original_name,  # Save original text (Ukrainian/Cyrillic) to database
                    quantity=quantity,
                    unit_price=price,
                    total_price=price * quantity,
                    confidence=confidence,
                )
            )
        
        # Accept receipt only if Darnitsa product is found
        receipt.status = "accepted" if (has_items and has_darnitsa) else "rejected"
        
        rejection_reason = None
        if not has_items:
            rejection_reason = "no_line_items"
        elif not has_darnitsa:
            rejection_reason = "no_darnitsa_products"
        
        if receipt.status == "accepted":
            LOGGER.info(
                "Receipt %s ACCEPTED: line_items=%d, has_darnitsa=%s",
                receipt_id,
                len(line_items),
                has_darnitsa,
            )
        else:
            # Log detailed rejection information
            item_names_sample = [item.get("original_name") or item.get("name", "")[:50] 
                                for item in line_items[:5]]
            LOGGER.warning(
                "Receipt %s REJECTED: reason=%s, line_items=%d, has_darnitsa=%s, merchant=%s, sample_items=%s",
                receipt_id,
                rejection_reason,
                len(line_items),
                has_darnitsa,
                receipt.merchant[:50] if receipt.merchant else "None",
                item_names_sample,
            )
            # Also log at INFO level for better visibility
            LOGGER.info(
                "Receipt %s REJECTED: reason=%s, line_items=%d, has_darnitsa=%s, merchant=%s, sample_items=%s",
                receipt_id,
                rejection_reason,
                len(line_items),
                has_darnitsa,
                receipt.merchant[:50] if receipt.merchant else "None",
                item_names_sample,
            )
        
        await session.commit()
        
        # Publish event if receipt was accepted
        if receipt.status == "accepted":
            event_bus = get_event_bus()
            await event_bus.publish(
                Event(
                    event_type=EVENT_RECEIPT_ACCEPTED,
                    payload={
                        "receipt_id": str(receipt_id),
                        "status": "accepted",
                    },
                )
            )


# Worker functions removed - rules evaluation is now triggered directly via evaluate()
# This file is kept for backward compatibility but worker loop is no longer needed

