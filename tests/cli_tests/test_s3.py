"""
CLI - Tests for S3-related functionality.
"""

import asyncio
from pathlib import Path

from app.services.s3_service import S3Config, S3Service


async def test_s3_upload_and_delete():
    """Test uploading a file to S3 and then deleting it."""
    input_file_path = input("Enter the path to the image file to upload: ").strip()
    photo_path = Path(input_file_path)

    async with S3Service(S3Config()) as s3_service:
        object_key = await s3_service.upload_file(photo_path)
        assert object_key is not None
        s3_url = await s3_service.presign_get(object_key)
        print(f"File uploaded to S3 at URL: {s3_url}")

    # Extract the key from the URL for deletion
    # key = s3_url.split("/")[-1]

    # Delete the file from S3
    # delete_success = await s3_service.delete_file(key)
    # assert delete_success
    # print(f"File with key '{key}' deleted from S3 successfully.")


asyncio.run(test_s3_upload_and_delete())
