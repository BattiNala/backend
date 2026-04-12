"""
Test for building S3 URLs."""

import asyncio

from app.services.s3_service import S3Config, S3Service


async def test_s3_url_building():
    """Test building an S3 URL from a bucket and key."""
    list_of_keys = input("Enter the S3 object keys (space-separated): ").strip().split(" ")

    async with S3Service(S3Config()) as s3_service:
        try:
            for key in list_of_keys:
                if not key:
                    raise ValueError("Object keys cannot be empty.")
                s3_url = s3_service.build_s3_url(key)
                print(f"Built S3 URL successfully:\n{s3_url}")
        except ValueError as e:
            print(f"Error building S3 URL: {e}")


asyncio.run(test_s3_url_building())
