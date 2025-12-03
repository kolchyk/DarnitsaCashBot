from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID

from libs.common import has_darnitsa_prefix
from libs.common.analytics import AnalyticsClient
from libs.common.constants import MAX_FILE_SIZE, SUPPORTED_CONTENT_TYPES
from libs.common.rate_limit import RateLimiter
from libs.common.storage import StorageClient
from libs.data.models import LineItem, Receipt
from libs.data.repositories import ReceiptRepository, StatisticsRepository, UserRepository

from libs.common import get_settings

from ..exceptions import EncryptionError
from ..dependencies import (
    get_analytics,
    get_receipt_rate_limiter,
    get_session_dep,
    get_storage_client,
)
from ..exceptions import UserAlreadyExistsError
from ..services.turbosms import TurboSmsClient
from ..schemas import (
    ReceiptLineItem,
    DarnitsaProduct,
    ManualReceiptDataRequest,
    ReceiptHistoryItem,
    ReceiptResponse,
    ReceiptUploadResponse,
    StatisticsResponse,
    UserResponse,
    UserUpsertRequest,
)

router = APIRouter()

logger = logging.getLogger(__name__)


async def _validate_upload_file(file: UploadFile) -> None:
    """Validate uploaded file size and content type."""
    if file.content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")


async def _upload_receipt_to_storage(
    storage: StorageClient,
    file: UploadFile,
    user_id: UUID,
    telegram_id: int,
) -> tuple[str, str]:
    """Upload receipt file to storage and return object key and checksum."""
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 10MB limit")
    
    checksum = hashlib.sha256(data).hexdigest()
    object_key = f"receipts/{user_id}/{uuid4()}.{file.filename.split('.')[-1]}"
    
    try:
        await storage.upload_bytes(
            key=object_key,
            content=data,
            content_type=file.content_type or "image/jpeg",
        )
    except RuntimeError as e:
        logger.error(
            f"Storage upload failed for user {telegram_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="Storage service temporarily unavailable. Please try again later.",
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected storage error for user {telegram_id}: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to upload receipt. Please try again later.",
        ) from e
    
    return object_key, checksum


async def _create_receipt_record(
    session: AsyncSession,
    receipt_repo: ReceiptRepository,
    user_id: UUID,
    object_key: str,
    checksum: str,
    telegram_id: int,
) -> Receipt:
    """Create receipt record in database."""
    try:
        receipt = await receipt_repo.create_receipt(
            user_id=user_id,
            upload_ts=datetime.now(timezone.utc),
            storage_object_key=object_key,
            checksum=checksum,
        )
        await session.commit()
        return receipt
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Failed to create receipt record for user {telegram_id}: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Receipt uploaded but failed to process. Please contact support.",
        ) from e


def _filter_darnitsa_products(
    line_items: list[LineItem],
    ocr_payload: dict | None,
) -> list[DarnitsaProduct]:
    """Filter Darnitsa products from line items."""
    darnitsa_products: list[DarnitsaProduct] = []
    
    if not ocr_payload or not isinstance(ocr_payload, dict):
        return darnitsa_products
    
    ocr_line_items = ocr_payload.get("line_items", [])
    ocr_lookup: dict[str, dict] = {}
    for entry in ocr_line_items:
        for key in (
            entry.get("original_name"),
            entry.get("name"),
            entry.get("normalized_name"),
        ):
            if isinstance(key, str):
                normalized_key = key.strip()
                if normalized_key and normalized_key not in ocr_lookup:
                    ocr_lookup[normalized_key] = entry
    
    for item in line_items:
        product_name = item.product_name.strip()
        ocr_entry = ocr_lookup.get(product_name) or ocr_lookup.get(product_name.upper())
        is_darnitsa = False
        if ocr_entry:
            is_darnitsa = bool(ocr_entry.get("is_darnitsa"))
            if not is_darnitsa:
                is_darnitsa = has_darnitsa_prefix(ocr_entry.get("original_name")) or has_darnitsa_prefix(
                    ocr_entry.get("normalized_name")
                )
        if not is_darnitsa:
            is_darnitsa = has_darnitsa_prefix(product_name)
        
        if not is_darnitsa:
            continue
        
        price_uah = item.unit_price / 100.0
        display_name = (
            (ocr_entry.get("original_name") if ocr_entry else None)
            or (ocr_entry.get("name") if ocr_entry else None)
            or product_name
        )
        darnitsa_products.append(
            DarnitsaProduct(
                name=display_name,
                price=price_uah,
                quantity=item.quantity,
            )
        )
    
    return darnitsa_products


@router.post("/users", response_model=UserResponse)
async def upsert_user(
    payload: UserUpsertRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session_dep),
):
    """Create or update a user."""
    try:
        user_repo = UserRepository(session)
        
        # Перевіряємо, чи користувач вже існує (для визначення нового користувача)
        existing_user = await user_repo.get_by_telegram(payload.telegram_id)
        is_new_user = existing_user is None
        # Перевіряємо, чи користувач додає номер телефону вперше
        had_phone_before = existing_user is not None and existing_user.phone_number is not None
        
        user = await user_repo.upsert_user(
            telegram_id=payload.telegram_id,
            phone_number=payload.phone_number,
            locale=payload.locale,
        )
        await session.commit()
        
        # Надсилаємо SMS новому користувачу з номером телефону або коли користувач додає номер вперше
        should_send_sms = (
            user.phone_number  # Є номер телефону
            and (
                is_new_user  # Новий користувач
                or (existing_user is not None and not had_phone_before)  # Додає номер телефону вперше
            )
        )
        
        if should_send_sms:
            logger.info(
                f"Sending welcome SMS to user {payload.telegram_id} "
                f"(new_user={is_new_user}, had_phone_before={had_phone_before})"
            )
            settings = get_settings()
            if settings.turbosms_enabled:
                async def send_welcome_sms():
                    """Функція для надсилання привітального SMS."""
                    turbosms_client = None
                    try:
                        logger.info(
                            f"Starting welcome SMS background task for user {payload.telegram_id}, "
                            f"phone={user.phone_number}"
                        )
                        turbosms_client = TurboSmsClient(settings)
                        message = (
                            "Вітаємо в Дарниця CashBot!\n"
                            "Надсилайте чеки з продукцією Дарниця та отримуйте бонуси. "
                            "Просто відправте фото чека в Telegram боті!"
                        )
                        success = await turbosms_client.send_sms(
                            phone_number=user.phone_number,
                            message=message,
                        )
                        if success:
                            logger.info(
                                f"Successfully sent welcome SMS to user {payload.telegram_id} "
                                f"(phone={user.phone_number})"
                            )
                        else:
                            logger.warning(
                                f"Failed to send welcome SMS to user {payload.telegram_id} "
                                f"(phone={user.phone_number}): send_sms returned False"
                            )
                    except Exception as e:
                        logger.error(
                            f"Failed to send welcome SMS to user {payload.telegram_id}: {e}",
                            exc_info=True,
                        )
                    finally:
                        if turbosms_client:
                            await turbosms_client.close()
                
                background_tasks.add_task(send_welcome_sms)
            else:
                logger.warning(
                    f"TurboSMS is disabled (TURBOSMS_ENABLED=False), "
                    f"skipping welcome SMS for user {payload.telegram_id}"
                )
        
        return UserResponse(
            id=user.id,
            telegram_id=user.telegram_id,
            locale=user.locale,
            has_phone=bool(user.phone_number),
        )
    except IntegrityError as e:
        await session.rollback()
        # Check if it's a unique constraint violation on telegram_id
        if "telegram_id" in str(e).lower() or "unique" in str(e).lower():
            raise UserAlreadyExistsError(payload.telegram_id) from e
        raise
    except ValueError as e:
        # Encryption/decryption errors raise ValueError
        await session.rollback()
        logger.error(
            f"Encryption error while upserting user: telegram_id={payload.telegram_id}, error={str(e)}",
            exc_info=True,
        )
        raise EncryptionError(f"Encryption error: {str(e)}", payload.telegram_id) from e


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
    """Upload a receipt image for processing."""
    # Check user exists
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check phone number is provided
    if not user.phone_number:
        raise HTTPException(
            status_code=400,
            detail="Phone number is required for payout. Please share your phone number using /change_phone command.",
        )
    
    # Validate file
    await _validate_upload_file(file)
    
    # Check rate limit
    allowed = await limiter.check(str(telegram_id))
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many uploads. Please wait a minute.")
    
    # Upload to storage
    object_key, checksum = await _upload_receipt_to_storage(
        storage, file, user.id, telegram_id
    )
    
    # Create receipt record
    receipt_repo = ReceiptRepository(session)
    receipt = await _create_receipt_record(
        session, receipt_repo, user.id, object_key, checksum, telegram_id
    )
    
    # Record analytics event
    payload = {
        "receipt_id": str(receipt.id),
        "user_id": str(user.id),
        "storage_key": object_key,
        "checksum": checksum,
        "telegram_id": telegram_id,
    }
    await analytics.record("receipt_uploaded", payload)
    
    # Trigger QR code processing in background
    async def process_receipt():
        try:
            logger.info(f"Starting QR code processing for receipt {receipt.id}, storage_key={object_key}")
            from apps.api_gateway.services.ocr.worker import process_message
            await process_message({
                "receipt_id": str(receipt.id),
                "storage_key": object_key,
            })
            logger.info(f"QR code processing completed for receipt {receipt.id}")
        except Exception as e:
            logger.error(
                f"Failed to process receipt {receipt.id}: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
    
    background_tasks.add_task(process_receipt)
    
    return ReceiptUploadResponse(
        receipt=ReceiptResponse(receipt_id=receipt.id, status=receipt.status),
        queue_reference="receipts.incoming",
    )


@router.get("/receipts/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt_status(
    receipt_id: UUID,
    session: AsyncSession = Depends(get_session_dep),
):
    # Load receipt with line items preloaded to avoid N+1 queries
    stmt = (
        select(Receipt)
        .options(selectinload(Receipt.line_items))
        .where(Receipt.id == receipt_id)
    )
    result = await session.execute(stmt)
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    # Check if QR code processing failed by looking at ocr_payload
    ocr_payload = receipt.ocr_payload
    if ocr_payload and isinstance(ocr_payload, dict):
        # If ocr_payload has error field, it means QR code processing failed
        error_type = ocr_payload.get("type")
        if ocr_payload.get("error") or error_type in (
            "unreadable_image",
            "tesseract_failure",
            "qr_code_not_found",
            "scraping_failed",
            "parsing_failed",
            "processing_error",
        ):
            await session.commit()
            return ReceiptResponse(receipt_id=receipt.id, status="rejected")
    
    # Filter Darnitsa products from preloaded line items
    darnitsa_products: list[DarnitsaProduct] = []
    all_line_items: list[ReceiptLineItem] = []
    
    if receipt.status in ("processing", "accepted"):
        darnitsa_products = _filter_darnitsa_products(
            receipt.line_items,
            receipt.ocr_payload,
        )
        
        # Extract all line items from ocr_payload
        if ocr_payload and isinstance(ocr_payload, dict):
            ocr_line_items = ocr_payload.get("line_items", [])
            for item in ocr_line_items:
                price_kopecks = item.get("price")
                price_uah = float(price_kopecks) / 100.0 if price_kopecks else 0.0
                all_line_items.append(
                    ReceiptLineItem(
                        name=item.get("name", ""),
                        quantity=item.get("quantity", 1),
                        price=price_uah,
                    )
                )
    
    # Commit read-only transaction to avoid ROLLBACK log noise
    await session.commit()
    
    return ReceiptResponse(
        receipt_id=receipt.id,
        status=receipt.status,
        darnitsa_products=darnitsa_products if darnitsa_products else None,
        line_items=all_line_items if all_line_items else None,
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
            "original_name": name,
            "normalized_name": name.upper(),
            "quantity": quantity,
            "price": price_kopecks,
            "confidence": 1.0,  # Manual input has full confidence
            "sku_code": None,
            "sku_match_score": 0.0,
            "is_darnitsa": has_darnitsa_prefix(name),
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
            from apps.api_gateway.services.rules.service import evaluate
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
                payout_reference=None,  # Payout provider integration removed
                payout_status=bonus.payout_status if bonus else None,
            )
        )
    # Commit read-only transaction to avoid ROLLBACK log noise
    await session.commit()
    return history


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(
    session: AsyncSession = Depends(get_session_dep),
):
    """Get system statistics: user count, receipt count, bonus transaction count."""
    stats_repo = StatisticsRepository(session)
    stats = await stats_repo.get_statistics()
    # Commit read-only transaction to avoid ROLLBACK log noise
    await session.commit()
    return StatisticsResponse(**stats)

