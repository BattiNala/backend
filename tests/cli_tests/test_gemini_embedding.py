"""CLI smoke test for Gemini text and image embeddings."""

import asyncio
import os
from pathlib import Path

from app.core.config import settings
from app.services.gemini_embedding_service import GeminiEmbeddingService


def _has_real_key() -> bool:
    """Return True when Gemini API key is configured for live calls."""
    value: str | None = getattr(settings, "GEMINI_API_KEY", None)
    return bool(value and value != "api-key-placeholder")


def _print_result(label: str, embedding: list[float]) -> None:
    """Print embedding metadata in a readable format."""
    print(f"\n== {label} ==")
    print("dimensions:", len(embedding))
    print("preview:", embedding[:8])


async def run_smoke_test() -> None:
    """Run Gemini embedding requests against real provider endpoints."""
    if not _has_real_key():
        print("skipped: GEMINI_API_KEY is not configured")
        return

    image_path = Path(
        os.environ.get(
            "GEMINI_EMBED_TEST_IMAGE_PATH",
            str(Path(__file__).resolve().parent / "img.png"),
        )
    )

    if not image_path.exists():
        raise RuntimeError(
            f"Image path does not exist: {image_path}. "
            "Set GEMINI_EMBED_TEST_IMAGE_PATH to a valid image file."
        )

    image_embedding = await GeminiEmbeddingService.generate_image_embedding(str(image_path))
    _print_result("Image Embedding", image_embedding)


asyncio.run(run_smoke_test())
