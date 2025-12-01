from __future__ import annotations

import io
import logging
from typing import BinaryIO

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from libs.common import AppSettings, get_settings

logger = logging.getLogger(__name__)


class StorageClient:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._session = aioboto3.Session()

    async def upload_bytes(self, *, key: str, content: bytes, content_type: str) -> str:
        try:
            async with self._client() as client:
                await client.put_object(
                    Bucket=self.settings.storage_bucket,
                    Key=key,
                    Body=content,
                    ContentType=content_type,
                )
            return key
        except EndpointConnectionError as e:
            logger.error(
                f"Failed to connect to storage endpoint: {self.settings.storage_endpoint}. "
                f"Error: {str(e)}",
                exc_info=True,
            )
            raise RuntimeError(
                f"Storage service unavailable. Please check STORAGE_ENDPOINT configuration."
            ) from e
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                f"Storage client error during upload: {error_code}. Key: {key}",
                exc_info=True,
            )
            raise RuntimeError(f"Storage upload failed: {error_code}") from e

    async def download(self, key: str) -> bytes:
        try:
            async with self._client() as client:
                obj = await client.get_object(
                    Bucket=self.settings.storage_bucket,
                    Key=key,
                )
                return await obj["Body"].read()
        except EndpointConnectionError as e:
            logger.error(
                f"Failed to connect to storage endpoint: {self.settings.storage_endpoint}. "
                f"Error: {str(e)}",
                exc_info=True,
            )
            raise RuntimeError(
                f"Storage service unavailable. Please check STORAGE_ENDPOINT configuration."
            ) from e
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                f"Storage client error during download: {error_code}. Key: {key}",
                exc_info=True,
            )
            raise RuntimeError(f"Storage download failed: {error_code}") from e

    async def upload_stream(self, *, key: str, stream: BinaryIO, content_type: str) -> str:
        buffer = io.BytesIO(stream.read())
        return await self.upload_bytes(key=key, content=buffer.getvalue(), content_type=content_type)

    def _client(self):
        # Configure for MinIO compatibility (signature_version='s3v4')
        config = Config(signature_version="s3v4")
        client_kwargs = {
            "service_name": "s3",
            "aws_access_key_id": self.settings.storage_access_key,
            "aws_secret_access_key": self.settings.storage_secret_key,
            "region_name": self.settings.storage_region,
            "config": config,
        }
        # Only set endpoint_url if provided (None for AWS S3)
        if self.settings.storage_endpoint:
            client_kwargs["endpoint_url"] = self.settings.storage_endpoint
        return self._session.client(**client_kwargs)

