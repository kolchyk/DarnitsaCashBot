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
    async with async_session_factory() as session:
        receipt: Receipt | None = await session.get(Receipt, receipt_id)
        if not receipt:
            return
        storage = StorageClient(settings)
        image_bytes = await storage.download(payload["storage_key"])

        try:
            preprocess_result = await asyncio.to_thread(
                preprocess_image,
                image_bytes,
                save_intermediates=settings.ocr_save_preprocessed,
            )
            tesseract_result = await asyncio.to_thread(
                _run_tesseract,
                preprocess_result,
                settings,
            )
        except UnreadableImageError as exc:
            LOGGER.warning("Unreadable receipt %s: %s", receipt_id, exc)
            receipt.status = ReceiptStatus.REJECTED
            failure_payload = {"error": str(exc), "type": "unreadable_image"}
            receipt.ocr_payload = failure_payload
            await session.commit()
            await _publish_failure(payload, failure_payload)
            return
        except TesseractRuntimeError as exc:
            LOGGER.error("Tesseract failure for receipt %s: %s", receipt_id, exc)
            receipt.status = ReceiptStatus.REJECTED
            failure_payload = {"error": str(exc), "type": "tesseract_failure"}
            receipt.ocr_payload = failure_payload
            await session.commit()
            await _publish_failure(payload, failure_payload)
            return

        catalog_repo = CatalogRepository(session)
        catalog = await catalog_repo.list_active()
        catalog_aliases = {
            item.sku_code: [alias.lower() for alias in item.product_aliases] for item in catalog
        }

        structured_payload = await asyncio.to_thread(
            build_structured_payload,
            preprocess_metadata=preprocess_result.metadata,
            tesseract_stats=tesseract_result.stats,
            tokens_by_profile=tesseract_result.tokens_by_profile,
            catalog_aliases=catalog_aliases,
            settings=settings,
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

    # Trigger rules engine evaluation after OCR completes successfully
    try:
        from services.rules_engine.service import evaluate
        await evaluate({
            "receipt_id": str(receipt_id),
            "ocr_payload": structured_payload,
        })
    except Exception as e:
        LOGGER.error(
            f"Failed to evaluate receipt {receipt_id} in rules engine: {type(e).__name__}: {str(e)}",
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


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    # RabbitMQ removed - worker no longer consumes from queue
    # This worker should be called directly or via HTTP endpoint instead
    while True:
        await asyncio.sleep(60)  # Placeholder - no longer consuming from queue


def run():
    asyncio.run(run_worker())


if __name__ == "__main__":
    run()

