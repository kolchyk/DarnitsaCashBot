from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from uuid import UUID

from libs.common import configure_logging, get_settings
from libs.common.storage import StorageClient
from libs.data import async_session_factory
from libs.data.models import Receipt, ReceiptStatus
from libs.data.repositories import CatalogRepository

from .postprocess import build_structured_payload
from .preprocess import PreprocessResult, UnreadableImageError, preprocess_image
from .tesseract_runner import TesseractResult, TesseractRunner, TesseractRuntimeError

LOGGER = logging.getLogger(__name__)


async def process_message(payload: dict) -> None:
    settings = get_settings()
    receipt_id = UUID(payload["receipt_id"])
    storage_key = payload.get("storage_key", "unknown")
    
    LOGGER.info(
        "Starting OCR processing for receipt %s, storage_key=%s, languages=%s",
        receipt_id,
        storage_key,
        settings.ocr_languages,
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
            LOGGER.debug("Starting image preprocessing for receipt %s", receipt_id)
            preprocess_result = await asyncio.to_thread(
                preprocess_image,
                image_bytes,
                save_intermediates=settings.ocr_save_preprocessed,
            )
            LOGGER.info(
                "Preprocessing completed for receipt %s: original_size=%dx%d, deskew_angle=%.2f, residual_skew=%.2f",
                receipt_id,
                preprocess_result.metadata["original_shape"]["width"],
                preprocess_result.metadata["original_shape"]["height"],
                preprocess_result.metadata.get("deskew_angle", 0.0),
                preprocess_result.metadata.get("residual_skew", 0.0),
            )
            
            LOGGER.debug("Starting Tesseract OCR for receipt %s", receipt_id)
            tesseract_result = await asyncio.to_thread(
                _run_tesseract,
                preprocess_result,
                settings,
            )
            
            # Log Tesseract statistics
            total_tokens = sum(len(tokens) for tokens in tesseract_result.tokens_by_profile.values())
            LOGGER.info(
                "Tesseract OCR completed for receipt %s: total_tokens=%d, profiles=%s",
                receipt_id,
                total_tokens,
                list(tesseract_result.tokens_by_profile.keys()),
            )
            for profile_name, stats in tesseract_result.stats.items():
                LOGGER.debug(
                    "Tesseract profile '%s' stats: tokens=%d, mean_confidence=%.3f",
                    profile_name,
                    stats.get("token_count", 0),
                    stats.get("mean_confidence", 0.0),
                )
        except UnreadableImageError as exc:
            LOGGER.warning("Unreadable receipt %s: %s", receipt_id, exc, exc_info=True)
            receipt.status = ReceiptStatus.REJECTED
            failure_payload = {"error": str(exc), "type": "unreadable_image"}
            receipt.ocr_payload = failure_payload
            await session.commit()
            await _publish_failure(payload, failure_payload)
            return
        except TesseractRuntimeError as exc:
            LOGGER.error("Tesseract failure for receipt %s: %s", receipt_id, exc, exc_info=True)
            receipt.status = ReceiptStatus.REJECTED
            failure_payload = {"error": str(exc), "type": "tesseract_failure"}
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

        LOGGER.debug("Starting postprocessing for receipt %s", receipt_id)
        structured_payload = await asyncio.to_thread(
            build_structured_payload,
            preprocess_metadata=preprocess_result.metadata,
            tesseract_stats=tesseract_result.stats,
            tokens_by_profile=tesseract_result.tokens_by_profile,
            catalog_aliases=catalog_aliases,
            settings=settings,
        )
        
        # Log postprocessing results
        line_items = structured_payload.get("line_items", [])
        confidence_info = structured_payload.get("confidence", {})
        LOGGER.info(
            "Postprocessing completed for receipt %s: line_items=%d, merchant=%s, total=%s, "
            "mean_confidence=%.3f, manual_review=%s, anomalies=%s",
            receipt_id,
            len(line_items),
            structured_payload.get("merchant"),
            structured_payload.get("total"),
            confidence_info.get("mean", 0.0),
            structured_payload.get("manual_review_required", False),
            structured_payload.get("anomalies", []),
        )
        
        # Log details about recognized line items
        if line_items:
            LOGGER.debug("Recognized line items for receipt %s:", receipt_id)
            for idx, item in enumerate(line_items, 1):
                sku_info = f", sku={item.get('sku_code')}" if item.get("sku_code") else ""
                sku_score = f", sku_score={item.get('sku_match_score', 0):.3f}" if item.get("sku_match_score") else ""
                LOGGER.debug(
                    "  Item %d: name='%s', quantity=%d, price=%s, confidence=%.3f%s%s",
                    idx,
                    item.get("name", "")[:50],  # Truncate long names
                    item.get("quantity", 0),
                    item.get("price"),
                    item.get("confidence", 0.0),
                    sku_info,
                    sku_score,
                )

        artifact_manifest = await _persist_artifacts(
            storage,
            receipt_id,
            preprocess_result,
            tesseract_result,
            settings,
        )
        if artifact_manifest:
            structured_payload["artifacts"] = artifact_manifest

        receipt.ocr_payload = structured_payload
        if structured_payload.get("merchant"):
            receipt.merchant = structured_payload["merchant"]
        purchase_ts = structured_payload.get("purchase_ts")
        if purchase_ts:
            receipt.purchase_ts = datetime.fromisoformat(purchase_ts)
        receipt.status = ReceiptStatus.PROCESSING
        await session.commit()
        
        LOGGER.info(
            "OCR processing completed for receipt %s: status=%s, merchant=%s, line_items=%d, total=%s",
            receipt_id,
            receipt.status,
            receipt.merchant,
            len(line_items),
            structured_payload.get("total"),
        )

    # Trigger rules engine evaluation after OCR completes successfully
    LOGGER.debug("Triggering rules engine evaluation for receipt %s", receipt_id)
    try:
        from services.rules_engine.service import evaluate
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


def _run_tesseract(preprocess_result: PreprocessResult, settings):
    runner = TesseractRunner(settings)
    return runner.run(preprocess_result)


async def _persist_artifacts(
    storage: StorageClient,
    receipt_id: UUID,
    preprocess_result: PreprocessResult,
    tesseract_result: TesseractResult,
    settings,
) -> dict[str, dict]:
    artifacts = preprocess_result.artifacts + tesseract_result.artifacts
    manifest: dict[str, dict] = {}
    for artifact in artifacts:
        key = f"{settings.ocr_storage_prefix}/{receipt_id}/{artifact.name}"
        await storage.upload_bytes(key=key, content=artifact.content, content_type=artifact.content_type)
        manifest[artifact.name] = {
            "storage_key": key,
            "content_type": artifact.content_type,
            "metadata": artifact.metadata,
        }
    return manifest


async def _publish_failure(payload: dict, failure_payload: dict) -> None:
    # RabbitMQ removed - failures are now stored in database only
    pass


# Worker functions removed - OCR processing is now triggered directly via process_message()
# This file is kept for backward compatibility but worker loop is no longer needed


if __name__ == "__main__":
    run()

