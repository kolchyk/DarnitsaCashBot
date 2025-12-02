from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path
from typing import BinaryIO

from libs.common import AppSettings, get_settings

logger = logging.getLogger(__name__)


class StorageClient:
    """Minimal async-friendly file storage used for the MVP."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._base_path = Path(self.settings.storage_base_dir).expanduser().resolve()
        self._base_path.mkdir(parents=True, exist_ok=True)

    async def upload_bytes(self, *, key: str, content: bytes, content_type: str) -> str:  # noqa: ARG002
        file_path = self._full_path(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(file_path.write_bytes, content)
        return key

    async def download(self, key: str) -> bytes:
        file_path = self._full_path(key)
        try:
            return await asyncio.to_thread(file_path.read_bytes)
        except FileNotFoundError as exc:  # pragma: no cover - defensive guard
            logger.error("Stored object missing on disk: %s", file_path)
            raise RuntimeError(f"Stored object missing: {key}") from exc

    async def upload_stream(self, *, key: str, stream: BinaryIO, content_type: str) -> str:  # noqa: ARG002
        buffer = io.BytesIO(stream.read())
        return await self.upload_bytes(key=key, content=buffer.getvalue(), content_type="application/octet-stream")

    def _full_path(self, key: str) -> Path:
        normalized = key.lstrip("/\\")
        return self._base_path / normalized

