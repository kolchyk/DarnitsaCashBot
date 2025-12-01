#!/usr/bin/env python3
"""
Скрипт для проверки подключения к Cloudflare R2 (или другому S3-совместимому хранилищу).

Использование:
    python scripts/test_r2_connection.py

Или на Heroku:
    heroku run python scripts/test_r2_connection.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from libs.common.config import get_settings
from libs.common.storage import StorageClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_connection():
    """Тестирует подключение к хранилищу и базовые операции."""
    settings = get_settings()
    storage = StorageClient(settings)

    logger.info("=" * 60)
    logger.info("Тестирование подключения к хранилищу")
    logger.info("=" * 60)
    logger.info(f"Endpoint: {settings.storage_endpoint or 'AWS S3 (default)'}")
    logger.info(f"Bucket: {settings.storage_bucket}")
    logger.info(f"Region: {settings.storage_region}")
    logger.info(f"Access Key: {settings.storage_access_key[:8]}..." if settings.storage_access_key else "Not set")
    logger.info("=" * 60)

    try:
        # Тест 1: Загрузка тестового файла
        logger.info("\n[Тест 1] Загрузка тестового файла...")
        test_content = b"This is a test file for R2 connection verification."
        test_key = "test/connection-test.txt"

        uploaded_key = await storage.upload_bytes(
            key=test_key,
            content=test_content,
            content_type="text/plain",
        )
        logger.info(f"✅ Файл успешно загружен: {uploaded_key}")

        # Тест 2: Скачивание файла
        logger.info("\n[Тест 2] Скачивание тестового файла...")
        downloaded_content = await storage.download(test_key)
        if downloaded_content == test_content:
            logger.info("✅ Файл успешно скачан, содержимое совпадает")
        else:
            logger.error("❌ Содержимое файла не совпадает!")
            return False

        # Тест 3: Загрузка бинарного файла (имитация изображения)
        logger.info("\n[Тест 3] Загрузка бинарного файла (имитация изображения)...")
        image_content = b"\x89PNG\r\n\x1a\n" + b"x" * 1000  # Минимальный PNG заголовок + данные
        image_key = "test/test-image.png"

        await storage.upload_bytes(
            key=image_key,
            content=image_content,
            content_type="image/png",
        )
        logger.info(f"✅ Бинарный файл успешно загружен: {image_key}")

        logger.info("\n" + "=" * 60)
        logger.info("✅ Все тесты пройдены успешно!")
        logger.info("=" * 60)
        logger.info("\nПримечание: Тестовые файлы были загружены в bucket.")
        logger.info("Вы можете удалить их вручную через Cloudflare Dashboard или")
        logger.info("настроить lifecycle policy для автоматической очистки.")

        return True

    except Exception as e:
        logger.error("\n" + "=" * 60)
        logger.error("❌ Ошибка при тестировании подключения")
        logger.error("=" * 60)
        logger.error(f"Тип ошибки: {type(e).__name__}")
        logger.error(f"Сообщение: {str(e)}", exc_info=True)
        logger.error("\nВозможные причины:")
        logger.error("1. Неправильный endpoint URL")
        logger.error("2. Неправильные Access Key или Secret Key")
        logger.error("3. Bucket не существует или имя указано неверно")
        logger.error("4. Проблемы с сетью или доступом")
        logger.error("5. Недостаточно прав у API токена")
        return False


async def main():
    """Главная функция."""
    success = await test_connection()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

