from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from libs.common import has_darnitsa_prefix
from libs.common.constants import ELIGIBILITY_WINDOW_DAYS, MAX_RECEIPTS_PER_DAY
from libs.data import async_session_factory
from libs.data.models import LineItem, Receipt
from libs.data.repositories import ReceiptRepository
from apps.api_gateway.services.bonus.service import trigger_payout_for_receipt

LOGGER = logging.getLogger(__name__)


def _is_darnitsa_item(item: dict) -> bool:
    """Return True if the OCR item contains a Darnitsa prefix."""
    if item.get("is_darnitsa"):
        return True
    for field in ("original_name", "name", "normalized_name"):
        if has_darnitsa_prefix(item.get(field)):
            return True
    return False


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
        has_darnitsa = False
        
        LOGGER.info(
            "Evaluating receipt %s: line_items=%d, daily_count=%d/%d, merchant=%s",
            receipt_id,
            len(line_items),
            daily_count,
            MAX_RECEIPTS_PER_DAY,
            receipt.merchant[:50] if receipt.merchant else "None",
        )
        
        if not line_items:
            LOGGER.warning("Receipt %s contains no OCR line items", receipt_id)
        
        for item in line_items:
            # Get original text - check both 'name' and 'original_name' fields
            original_name = item.get("original_name") or item.get("name", "")
            if not original_name:
                LOGGER.debug("Skipping item with empty name: %s", item)
                continue
            
            if not has_darnitsa and _is_darnitsa_item(item):
                has_darnitsa = True
                LOGGER.info("Receipt %s: detected Darnitsa prefix in '%s'", receipt_id, original_name[:100])
            elif not has_darnitsa:
                LOGGER.debug(
                    "Receipt %s: item without Darnitsa prefix: '%s'",
                    receipt_id,
                    original_name[:100],
                )
            
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
        
        if receipt.status == "accepted":
            await trigger_payout_for_receipt(receipt.id)

