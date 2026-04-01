"""
Utility functions for handling S3 interactions, including photo uploads and URL generation.
"""

import os
import tempfile
from pathlib import Path

import aiofiles
import aiofiles.os
from fastapi import HTTPException, UploadFile

from app.core.logger import get_logger
from app.services.s3_service import S3Config, S3Service

logger = get_logger("api.issues")


def _get_s3_service() -> S3Service:
    """Create and return an S3Service instance."""
    return S3Service(S3Config())


def populate_attachment_urls(issue) -> None:
    """Replace attachment paths with full S3 URLs."""
    s3 = _get_s3_service()
    for attachment in issue.attachments:
        attachment.path = s3.build_s3_url(attachment.path)


async def safe_upload_photos_to_s3(photos: list[UploadFile]) -> tuple[list[str], list[str]]:
    """
    Safely upload photos to S3, ensuring cleanup of temporary files and uploaded objects on failure.
    Returns a tuple of (attachment_paths, temp_paths) for successful uploads.
    """
    try:
        async with _get_s3_service() as s3:
            return await upload_photos_to_s3(photos, s3)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="An error occurred while uploading photos.",
        ) from e


async def upload_photos_to_s3(
    photos: list[UploadFile],
    s3: S3Service,
) -> tuple[list[str], list[str]]:
    """
    Upload photos to S3 and return their object keys along with temporary file paths.
    """
    attachment_paths: list[str] = []
    temp_paths: list[str] = []
    for photo in photos:
        fd, temp_path = tempfile.mkstemp(suffix=Path(photo.filename).suffix)
        os.close(fd)
        temp_paths.append(temp_path)

        async with aiofiles.open(temp_path, "wb") as out_file:
            while chunk := await photo.read(1024 * 1024):
                await out_file.write(chunk)

        try:
            object_key = await s3.upload_file(Path(temp_path))
        except Exception:
            await delete_uploaded_s3_objects(s3, attachment_paths)
            raise

        if not object_key:
            await delete_uploaded_s3_objects(s3, attachment_paths)
            raise RuntimeError(f"Failed to upload photo: {photo.filename}")

        attachment_paths.append(object_key)
    return attachment_paths, temp_paths


async def delete_temp_files(temp_paths):
    """Delete temporary files used for photo uploads."""
    for tmp in temp_paths:
        try:
            await aiofiles.os.remove(tmp)
        except FileNotFoundError:
            # If the file was already removed, we can ignore this error
            pass


async def delete_uploaded_s3_objects(s3: S3Service, object_keys: list[str]) -> None:
    """Best-effort delete for uploaded S3 objects."""
    for object_key in object_keys:
        deleted = await s3.delete_file(object_key)
        if not deleted:
            logger.warning("Failed to delete uploaded attachment from storage: key=%s", object_key)


async def delete_uploaded_files(object_keys: list[str]) -> None:
    """Best-effort cleanup for uploaded S3 objects after request failure."""
    if not object_keys:
        return

    try:
        async with _get_s3_service() as s3:
            await delete_uploaded_s3_objects(s3, object_keys)
    # pylint: disable=broad-exception-caught
    except Exception:
        logger.exception("Failed to clean up uploaded attachments: keys=%s", object_keys)
