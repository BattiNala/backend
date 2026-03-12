"""
Async S3-compatible storage wrapper (AWS S3 / MinIO / Cloudflare R2)
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
from types import TracebackType
from typing import Any
from uuid import uuid4

import aioboto3
import aiofiles
from botocore.config import Config
from botocore.exceptions import ClientError
from mypy_boto3_s3.client import S3Client

from app.core.config import settings


@dataclass(frozen=True)
class S3Config:
    bucket_name: str = settings.S3_BUCKET_NAME
    region_name: str = settings.S3_REGION_NAME
    endpoint_url: str | None = settings.S3_ENDPOINT_URL
    aws_access_key_id: str | None = settings.S3_ACCESS_KEY_ID
    aws_secret_access_key: str | None = settings.S3_SECRET_ACCESS_KEY
    force_path_style: bool | None = settings.S3_FORCE_PATH_STYLE


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

    def __init__(self, cfg: S3Config) -> None:
        self.cfg: S3Config = cfg
        self.bucket_name: str = cfg.bucket_name
        self._session: aioboto3.Session = aioboto3.Session()

        self._client_cm: Any | None = None
        self.client: S3Client | None = None

    async def __aenter__(self) -> "S3Service":

        force_path_style: bool | None = self.cfg.force_path_style
        if force_path_style is None:
            force_path_style = bool(self.cfg.endpoint_url)

        config: Config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if force_path_style else "virtual"},
        )

        self._client_cm = self._session.client(
            "s3",
            region_name=self.cfg.region_name,
            endpoint_url=self.cfg.endpoint_url,
            aws_access_key_id=self.cfg.aws_access_key_id,
            aws_secret_access_key=self.cfg.aws_secret_access_key,
            config=config,
        )

        self.client = await self._client_cm.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:

        if self._client_cm is not None:
            await self._client_cm.__aexit__(exc_type, exc, tb)

        self.client = None
        self._client_cm = None

    def build_s3_url(self, object_key: str) -> str:
        """
        Build the full S3 URL for an object key.

        AWS default:
            https://bucket.s3.region.amazonaws.com/key

        Custom endpoint:
        - path-style:    https://endpoint/bucket/key
        - virtual-style: https://bucket.endpoint/key
        """

        key: str = object_key.lstrip("/")

        if self.cfg.endpoint_url:
            base_url: str = self.cfg.endpoint_url.rstrip("/")

            force_path_style: bool = (
                self.cfg.force_path_style if self.cfg.force_path_style is not None else True
            )

            if force_path_style:
                return f"{base_url}/{self.bucket_name}/{key}"

            scheme, rest = base_url.split("://", 1)
            return f"{scheme}://{self.bucket_name}.{rest}/{key}"

        region: str = self.cfg.region_name or "us-east-1"
        return f"https://{self.bucket_name}.s3.{region}.amazonaws.com/{key}"

    async def upload_file(self, file_path: Path, prefix: str = "images") -> str | None:
        """Upload a file to S3 and return the object key."""

        if self.client is None:
            raise RuntimeError("S3Service not initialized")

        file_path = Path(file_path)

        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(file_path)

        ext: str = file_path.suffix
        now: datetime = datetime.now(timezone.utc)

        object_key: str = f"{prefix}/{now:%Y/%m}/{uuid4().hex}{ext}"

        try:
            async with aiofiles.open(file_path, "rb") as f:
                body: bytes = await f.read()

            await self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=body,
            )

            return object_key

        except ClientError as e:
            print(e)
            return None

    async def download_file(self, object_key: str, file_path: Path) -> bool:
        """Download a file from S3 by its object key."""

        if self.client is None:
            raise RuntimeError("S3Service not initialized")

        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            resp = await self.client.get_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )

            stream = resp["Body"]

            async with aiofiles.open(file_path, "wb") as f:
                while True:
                    chunk: bytes = await stream.read(1024 * 1024)

                    if not chunk:
                        break

                    await f.write(chunk)

            await stream.close()

            return True

        except ClientError as e:
            print(e)
            return False

    async def delete_file(self, object_key: str) -> bool:
        """Delete a file from S3 by its object key."""

        if self.client is None:
            raise RuntimeError("S3Service not initialized")

        try:
            await self.client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )

            return True

        except ClientError as e:
            print(e)
            return False

    async def list_files(self, prefix: str = "") -> list[str]:
        """List all object keys in the bucket with the given prefix."""

        if self.client is None:
            raise RuntimeError("S3Service not initialized")

        keys: list[str] = []

        continuation_token: str | None = None

        try:
            while True:
                kwargs: dict[str, Any] = {
                    "Bucket": self.bucket_name,
                    "Prefix": prefix,
                }

                if continuation_token:
                    kwargs["ContinuationToken"] = continuation_token

                resp = await self.client.list_objects_v2(**kwargs)

                contents = resp.get("Contents", [])

                keys.extend(obj["Key"] for obj in contents)

                if resp.get("IsTruncated"):
                    continuation_token = resp["NextContinuationToken"]
                else:
                    break

            return keys

        except ClientError as e:
            print(e)
            return []

    async def presign_get(self, object_key: str, expiration: int = 3600) -> str | None:

        if self.client is None:
            raise RuntimeError("S3Service not initialized")

        try:
            return await self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": object_key,
                },
                ExpiresIn=expiration,
            )

        except ClientError as e:
            print(e)
            return None
