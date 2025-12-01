from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from libs.common.analytics import AnalyticsClient
from libs.common.rate_limit import RateLimiter
from libs.common.storage import StorageClient
from libs.data.models import LineItem, Receipt
from libs.data.repositories import ReceiptRepository, UserRepository

from ..dependencies import (
    get_analytics,
    get_receipt_rate_limiter,
    get_session_dep,
    get_storage_client,
)
from ..schemas import (
    DarnitsaProduct,
    ManualReceiptDataRequest,
    ReceiptHistoryItem,
    ReceiptResponse,
    ReceiptUploadResponse,
    UserResponse,
    UserUpsertRequest,
)

router = APIRouter()

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024
SUPPORTED_CONTENT_TYPES = {"image/jpeg", "image/png"}


@router.post("/users", response_model=UserResponse)
async def upsert_user(
    payload: UserUpsertRequest,
    session: AsyncSession = Depends(get_session_dep),
):
    try:
        user_repo = UserRepository(session)
        user = await user_repo.upsert_user(
            telegram_id=payload.telegram_id,
            phone_number=payload.phone_number,
            locale=payload.locale,
        )
        await session.commit()
        return UserResponse(
            id=user.id,
            telegram_id=user.telegram_id,
            locale=user.locale,
            has_phone=bool(user.phone_number),
        )
    except IntegrityError as e:
        await session.rollback()
        logger.error(
            f"Database integrity error while upserting user: telegram_id={payload.telegram_id}, "
            f"error={str(e)}",
            exc_info=True,
        )
        # Check if it's a unique constraint violation (duplicate telegram_id)
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail=f"User with telegram_id {payload.telegram_id} already exists",
            ) from e
        raise HTTPException(
            status_code=400,
            detail="Database constraint violation",
        ) from e
    except ValueError as e:
        await session.rollback()
        logger.error(
            f"Value error while upserting user: telegram_id={payload.telegram_id}, "
            f"error={str(e)}",
            exc_info=True,
        )
        # Likely an encryption error
        raise HTTPException(
            status_code=500,
            detail="Internal server error during user registration",
        ) from e
    except SQLAlchemyError as e:
        await session.rollback()
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(
            f"Database error while upserting user: telegram_id={payload.telegram_id}, "
            f"error_type={error_type}, error={error_msg}",
            exc_info=True,
        )
        # Include more details in response for debugging (can be removed in production)
        detail_msg = f"Database error occurred: {error_type}"
        if "connection" in error_msg.lower() or "connect" in error_msg.lower():
            detail_msg += " - Database connection issue"
        elif "relation" in error_msg.lower() or "table" in error_msg.lower() or "does not exist" in error_msg.lower():
            detail_msg += " - Table or relation does not exist (migrations may be needed)"
        raise HTTPException(
            status_code=500,
            detail=detail_msg,
        ) from e
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Unexpected error while upserting user: telegram_id={payload.telegram_id}, "
            f"error_type={type(e).__name__}, error={str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from e


@router.post("/receipts", response_model=ReceiptUploadResponse)
async def upload_receipt(
    telegram_id: int,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_session_dep),
    storage: StorageClient = Depends(get_storage_client),
    analytics: AnalyticsClient = Depends(get_analytics),
    limiter: RateLimiter = Depends(get_receipt_rate_limiter),
):
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if file.content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 10MB limit")

    allowed = await limiter.check(str(telegram_id))
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many uploads. Please wait a minute.")

    checksum = hashlib.sha256(data).hexdigest()
    object_key = f"receipts/{user.id}/{uuid4()}.{file.filename.split('.')[-1]}"
    
    try:
        await storage.upload_bytes(key=object_key, content=data, content_type=file.content_type or "image/jpeg")
    except RuntimeError as e:
        await session.rollback()
        logger.error(
            f"Storage upload failed for user {telegram_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="Storage service temporarily unavailable. Please try again later.",
        ) from e
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Unexpected storage error for user {telegram_id}: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to upload receipt. Please try again later.",
        ) from e

    receipt_repo = ReceiptRepository(session)
    try:
        receipt = await receipt_repo.create_receipt(
            user_id=user.id,
            upload_ts=datetime.now(timezone.utc),
            storage_object_key=object_key,
            checksum=checksum,
        )
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Failed to create receipt record for user {telegram_id}: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        # Note: File was uploaded but receipt record failed - this is a partial failure
        raise HTTPException(
            status_code=500,
            detail="Receipt uploaded but failed to process. Please contact support.",
        ) from e

    payload = {
        "receipt_id": str(receipt.id),
        "user_id": str(user.id),
        "storage_key": object_key,
        "checksum": checksum,
        "telegram_id": telegram_id,
    }
    await analytics.record("receipt_uploaded", payload)
    
    # Trigger OCR processing in background
    async def process_ocr():
        try:
            logger.info(f"Starting OCR processing for receipt {receipt.id}, storage_key={object_key}")
            from services.ocr_worker.worker import process_message
            await process_message({
                "receipt_id": str(receipt.id),
                "storage_key": object_key,
            })
            logger.info(f"OCR processing completed for receipt {receipt.id}")
        except Exception as e:
            logger.error(
                f"Failed to process OCR for receipt {receipt.id}: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
    
    background_tasks.add_task(process_ocr)
    
    return ReceiptUploadResponse(
        receipt=ReceiptResponse(receipt_id=receipt.id, status=receipt.status),
        queue_reference="receipts.incoming",
    )


@router.get("/receipts/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt_status(
    receipt_id: UUID,
    session: AsyncSession = Depends(get_session_dep),
):
    stmt = select(Receipt).where(Receipt.id == receipt_id)
    result = await session.execute(stmt)
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    # Check if OCR failed by looking at ocr_payload
    ocr_payload = receipt.ocr_payload
    if ocr_payload and isinstance(ocr_payload, dict):
        # If ocr_payload has error field, it means OCR failed
        if ocr_payload.get("error") or ocr_payload.get("type") in ("unreadable_image", "tesseract_failure"):
            await session.commit()
            return ReceiptResponse(receipt_id=receipt.id, status="rejected")
    
    # Load line items and filter Darnitsa products
    darnitsa_products: list[DarnitsaProduct] = []
    if receipt.status in ("processing", "accepted"):
        # Keywords for identifying Darnitsa products (same as in rules_engine)
        DARNITSA_KEYWORDS_CYRILLIC = [
            "дарниця", "дарница", "дарниці", "дарницю", "дарницею",
        ]
        DARNITSA_KEYWORDS_LATIN = [
            "darnitsa", "darnitsia",  # транслитерация через unidecode
        ]
        
        line_items_stmt = select(LineItem).where(LineItem.receipt_id == receipt_id)
        line_items_result = await session.execute(line_items_stmt)
        line_items = line_items_result.scalars().all()
        
        # Также проверяем OCR payload для оригинального текста
        ocr_payload = receipt.ocr_payload
        ocr_line_items = ocr_payload.get("line_items", []) if isinstance(ocr_payload, dict) else []
        ocr_name_map = {item.get("name", ""): item.get("original_name", item.get("name", "")) 
                        for item in ocr_line_items}
        
        for item in line_items:
            name_lower = item.product_name.lower()
            # Проверяем нормализованное имя (транслитерация)
            found = any(keyword in name_lower for keyword in DARNITSA_KEYWORDS_LATIN)
            
            # Если не найдено, проверяем оригинальное имя из OCR payload
            if not found and ocr_name_map:
                original_name = ocr_name_map.get(item.product_name, "")
                if original_name:
                    original_lower = original_name.lower()
                    found = any(keyword in original_lower for keyword in DARNITSA_KEYWORDS_CYRILLIC)
            
            if found:
                # Convert price from kopecks to UAH
                price_uah = item.unit_price / 100.0
                # Используем оригинальное название, если доступно, иначе нормализованное
                display_name = ocr_name_map.get(item.product_name, item.product_name)
                if not display_name or display_name == item.product_name:
                    display_name = item.product_name
                darnitsa_products.append(
                    DarnitsaProduct(
                        name=display_name,
                        price=price_uah,
                        quantity=item.quantity,
                    )
                )
    
    # Commit read-only transaction to avoid ROLLBACK log noise
    await session.commit()
    
    return ReceiptResponse(
        receipt_id=receipt.id,
        status=receipt.status,
        darnitsa_products=darnitsa_products if darnitsa_products else None,
    )


@router.post("/receipts/{receipt_id}/manual", response_model=ReceiptResponse)
async def submit_manual_receipt_data(
    receipt_id: UUID,
    data: ManualReceiptDataRequest,
    session: AsyncSession = Depends(get_session_dep),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    stmt = select(Receipt).where(Receipt.id == receipt_id)
    result = await session.execute(stmt)
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    # Build OCR payload from manual input
    line_items = []
    for item in data.line_items:
        name = item.get("name", "")
        quantity = int(item.get("quantity", 1))
        price_str = str(item.get("price", "0"))
        # Convert price to kopecks (minor units)
        try:
            price_float = float(price_str.replace(",", "."))
            price_kopecks = int(round(price_float * 100))
        except (ValueError, TypeError):
            price_kopecks = 0
        
        line_items.append({
            "name": name,
            "quantity": quantity,
            "price": price_kopecks,
            "confidence": 1.0,  # Manual input has full confidence
            "sku_code": None,
            "sku_match_score": 0.0,
        })
    
    ocr_payload = {
        "merchant": data.merchant,
        "purchase_ts": data.purchase_date,
        "total": None,
        "line_items": line_items,
        "confidence": {
            "mean": 1.0,
            "min": 1.0,
            "max": 1.0,
            "token_count": len(line_items),
            "auto_accept_candidate": True,
        },
        "preprocessing": {},
        "tesseract_stats": {},
        "manual_review_required": False,
        "anomalies": [],
        "manual_input": True,
    }
    
    receipt.ocr_payload = ocr_payload
    if data.merchant:
        receipt.merchant = data.merchant
    if data.purchase_date:
        try:
            receipt.purchase_ts = datetime.fromisoformat(data.purchase_date)
        except ValueError:
            pass
    receipt.status = "processing"
    await session.commit()
    
    # Trigger rules engine evaluation
    async def process_manual_receipt():
        try:
            from services.rules_engine.service import evaluate
            await evaluate({
                "receipt_id": str(receipt_id),
                "ocr_payload": ocr_payload,
            })
        except Exception as e:
            logger.error(
                f"Failed to evaluate manual receipt {receipt_id}: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
    
    background_tasks.add_task(process_manual_receipt)
    
    return ReceiptResponse(receipt_id=receipt.id, status=receipt.status)


@router.get("/history/{telegram_id}", response_model=list[ReceiptHistoryItem])
async def get_history(
    telegram_id: int,
    session: AsyncSession = Depends(get_session_dep),
):
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    receipt_repo = ReceiptRepository(session)
    receipts = await receipt_repo.history_for_user(user.id)
    history: list[ReceiptHistoryItem] = []
    for receipt in receipts:
        bonus = receipt.bonus_transaction
        history.append(
            ReceiptHistoryItem(
                receipt_id=receipt.id,
                status=receipt.status,
                uploaded_at=receipt.upload_ts,
                payout_reference=bonus.portmone_bill_id if bonus else None,
                payout_status=bonus.payout_status if bonus else None,
            )
        )
    # Commit read-only transaction to avoid ROLLBACK log noise
    await session.commit()
    return history

