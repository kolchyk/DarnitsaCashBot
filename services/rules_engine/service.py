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
from libs.common.portmone import PortmoneDirectClient
from libs.data import async_session_factory
from libs.data.models import LineItem, Receipt
from libs.data.repositories import ReceiptRepository

LOGGER = logging.getLogger(__name__)


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
        
        # Check for "Дарниця" in product names
        # Use case-insensitive search
        # Include different cases and spelling variants in Ukrainian
        has_darnitsa = False
        
        # Save all recognized products and check for Darnitsa
        LOGGER.info(
            "Evaluating receipt %s: line_items=%d, daily_count=%d/%d",
            receipt_id,
            len(line_items),
            daily_count,
            MAX_RECEIPTS_PER_DAY,
        )
        
        for item in line_items:
            # Get original text (now 'name' contains original text, not normalized)
            original_name = item.get("name", "")
            # Normalize for Latin keyword matching if needed
            normalized_name = unidecode(unicodedata.normalize("NFC", original_name)).upper()
            
            original_lower = original_name.lower()
            normalized_lower = normalized_name.lower()
            
            # Check for Darnitsa in original text (Cyrillic)
            if any(keyword in original_lower for keyword in DARNITSA_KEYWORDS_CYRILLIC):
                has_darnitsa = True
                LOGGER.debug("Found Darnitsa keyword (cyrillic) in item: '%s'", original_name[:50])
            # Check in normalized text (transliteration)
            elif any(keyword in normalized_lower for keyword in DARNITSA_KEYWORDS_LATIN):
                has_darnitsa = True
                LOGGER.debug("Found Darnitsa keyword (latin) in item: '%s'", normalized_name[:50])
            
            quantity = int(item.get("quantity", 1))
            price = item.get("price")
            if price is None:
                price = 0
            else:
                price = int(price)
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
            LOGGER.warning(
                "Receipt %s REJECTED: reason=%s, line_items=%d, has_darnitsa=%s",
                receipt_id,
                rejection_reason,
                len(line_items),
                has_darnitsa,
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

