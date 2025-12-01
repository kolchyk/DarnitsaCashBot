from __future__ import annotations

import io
from typing import BinaryIO

import aioboto3

from libs.common import AppSettings, get_settings


class StorageClient:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._session = aioboto3.Session()

    async def upload_bytes(self, *, key: str, content: bytes, content_type: str) -> str:
        async with self._client() as client:
            await client.put_object(
                Bucket=self.settings.storage_bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        return key

    async def download(self, key: str) -> bytes:
        async with self._client() as client:
            obj = await client.get_object(
                Bucket=self.settings.storage_bucket,
                Key=key,
            )
            return await obj["Body"].read()

    async def upload_stream(self, *, key: str, stream: BinaryIO, content_type: str) -> str:
        buffer = io.BytesIO(stream.read())
        return await self.upload_bytes(key=key, content=buffer.getvalue(), content_type=content_type)

    def _client(self):
        return self._session.client(
            "s3",
            endpoint_url=self.settings.storage_endpoint,
            aws_access_key_id=self.settings.storage_access_key,
            aws_secret_access_key=self.settings.storage_secret_key,
        )

