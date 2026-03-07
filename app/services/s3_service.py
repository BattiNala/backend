"""
Async S3-compatible storage wrapper (AWS S3 / MinIO / Cloudflare R2) using pathlib.

This version uses:
- aiobotocore for an async S3 client
- aiofiles for async disk I/O

Install:
  pip install aiobotocore aiofiles botocore

Providers
---------
AWS S3:
  endpoint_url=None (default), force_path_style=False (default)
MinIO:
  endpoint_url="http(s)://...", force_path_style=True (recommended)
Cloudflare R2:
  endpoint_url="https://<accountid>.r2.cloudflarestorage.com"
  region_name="auto" (commonly used), force_path_style=True (recommended)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from uuid import uuid4

import aiofiles
from aiobotocore.session import get_session
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings


@dataclass(frozen=True)
class S3Config:
    """Runtime configuration for an S3-compatible object storage backend."""

    bucket_name: str = settings.S3_BUCKET_NAME
    region_name: str = settings.S3_REGION_NAME
    endpoint_url: Optional[str] = settings.S3_ENDPOINT_URL
    aws_access_key_id: Optional[str] = settings.S3_ACCESS_KEY_ID
    aws_secret_access_key: Optional[str] = settings.S3_SECRET_ACCESS_KEY
    force_path_style: Optional[bool] = settings.S3_FORCE_PATH_STYLE  # allow None


class S3Service:
    """
    Minimal async service wrapper for S3-compatible storage.

    Usage
    -----
    cfg = S3Config(...)
    async with S3Service(cfg) as s3:
        key = await s3.upload_image(Path("local.png"))
        url = await s3.presign_get(key)
    """

    def __init__(self, cfg: S3Config):
        self.cfg = cfg
        self.bucket_name = cfg.bucket_name
        self._session = get_session()
        self._client_cm = None
        self.client = None

    async def __aenter__(self) -> "S3Service":
        force_path_style = self.cfg.force_path_style
        if force_path_style is None:
            force_path_style = bool(self.cfg.endpoint_url)

        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if force_path_style else "virtual"},
        )

        # aiobotocore returns an async context manager for clients
        self._client_cm = self._session.create_client(
            "s3",
            region_name=self.cfg.region_name,
            endpoint_url=self.cfg.endpoint_url,
            aws_access_key_id=self.cfg.aws_access_key_id,
            aws_secret_access_key=self.cfg.aws_secret_access_key,
            config=config,
        )
        self.client = await self._client_cm.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client_cm is not None:
            await self._client_cm.__aexit__(exc_type, exc, tb)
        self.client = None
        self._client_cm = None

    async def upload_image(
        self, file_path: Path, prefix: str = "images"
    ) -> Optional[str]:
        """
        Upload a local image file.

        Object key format:
            {prefix}/{YYYY}/{MM}/{uuid}{ext}
        """
        if self.client is None:
            raise RuntimeError(
                "S3Service client is not initialized. Use: async with S3Service(cfg) as s3: ..."
            )

        file_path = Path(file_path)
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = file_path.suffix
        now = datetime.now(timezone.utc)
        object_key = f"{prefix}/{now:%Y/%m}/{uuid4().hex}{ext}"

        try:
            async with aiofiles.open(file_path, "rb") as f:
                body = await f.read()

            await self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=body,
                # ContentType optional
                # ContentType="image/png",
            )
            return object_key
        except ClientError as e:
            print(f"Upload failed: {e}")
            return None

    async def download_file(self, object_key: str, file_path: Path) -> bool:
        """
        Download an object to a local path using GetObject (no listing).
        """
        if self.client is None:
            raise RuntimeError(
                "S3Service client is not initialized. Use: async with S3Service(cfg) as s3: ..."
            )

        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            resp = await self.client.get_object(Bucket=self.bucket_name, Key=object_key)
            stream = resp["Body"]  # aiobotocore StreamingBody

            async with aiofiles.open(file_path, "wb") as f:
                while True:
                    chunk = await stream.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    await f.write(chunk)

            # Make sure the stream is closed
            await stream.close()
            return True
        except ClientError as e:
            print(f"Download failed: {e}")
            return False

    async def delete_file(self, object_key: str) -> bool:
        """
        Delete an object by key.
        """
        if self.client is None:
            raise RuntimeError(
                "S3Service client is not initialized. Use: async with S3Service(cfg) as s3: ..."
            )

        try:
            await self.client.delete_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            print(f"Delete failed: {e}")
            return False

    async def list_files(self, prefix: str = "") -> List[str]:
        """
        List keys under a prefix (avoid in hot paths).
        """
        if self.client is None:
            raise RuntimeError(
                "S3Service client is not initialized. Use: async with S3Service(cfg) as s3: ..."
            )

        keys: List[str] = []
        try:
            # handle pagination
            continuation_token = None
            while True:
                kwargs = {"Bucket": self.bucket_name, "Prefix": prefix}
                if continuation_token:
                    kwargs["ContinuationToken"] = continuation_token

                resp = await self.client.list_objects_v2(**kwargs)
                keys.extend([obj["Key"] for obj in resp.get("Contents", [])])

                if resp.get("IsTruncated"):
                    continuation_token = resp.get("NextContinuationToken")
                else:
                    break

            return keys
        except ClientError as e:
            print(f"List failed: {e}")
            return []

    async def presign_get(
        self, object_key: str, expiration: int = 3600
    ) -> Optional[str]:
        """
        Generate a presigned GET URL.

        Note: generate_presigned_url is synchronous in botocore, but it's fast and
        doesn't do network I/O; safe to call inside async code.
        """
        if self.client is None:
            raise RuntimeError(
                "S3Service client is not initialized. Use: async with S3Service(cfg) as s3: ..."
            )

        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=expiration,
            )
        except ClientError as e:
            print(f"Presign failed: {e}")
            return None
