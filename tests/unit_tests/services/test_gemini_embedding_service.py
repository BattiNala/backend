# pylint: disable=protected-access
"""Tests for Gemini embedding service."""

import asyncio
import base64

import httpx
import pytest

from app.services import gemini_embedding_service as embedding_module
from app.services.gemini_embedding_service import GeminiEmbeddingService


class _FakeAsyncClient:
    """Async client test double for httpx.AsyncClient."""

    responses: list[httpx.Response] = []
    requests: list[dict] = []

    def __init__(self, *args, **kwargs):
        """Init."""
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Exit async context."""
        return None

    async def post(self, url, **kwargs):
        """Record outgoing request and return the next configured response."""
        self.__class__.requests.append({"url": url, **kwargs})
        return self.__class__.responses.pop(0)


def test_generate_embedding_returns_vector(monkeypatch):
    """Single embedding requests return the parsed vector."""
    monkeypatch.setattr(embedding_module.settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(
        embedding_module.settings,
        "GEMINI_EMBEDDING_MODEL",
        "gemini-embedding-2-preview",
    )
    monkeypatch.setattr(embedding_module.httpx, "AsyncClient", _FakeAsyncClient)

    _FakeAsyncClient.requests = []
    _FakeAsyncClient.responses = [
        httpx.Response(
            200,
            json={"embedding": {"values": [0.1, 0.2, 0.3]}},
            request=httpx.Request(
                "POST",
                GeminiEmbeddingService._embed_url("gemini-embedding-2-preview"),
            ),
        )
    ]

    result = asyncio.run(
        GeminiEmbeddingService.generate_embedding(
            "  overflowing garbage on the roadside  ",
            task_type="RETRIEVAL_DOCUMENT",
            title="Sanitation issue",
        )
    )

    assert result == [0.1, 0.2, 0.3]
    assert _FakeAsyncClient.requests[0]["url"] == GeminiEmbeddingService._embed_url(
        "gemini-embedding-2-preview"
    )
    assert _FakeAsyncClient.requests[0]["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert _FakeAsyncClient.requests[0]["json"] == {
        "model": "models/gemini-embedding-2-preview",
        "content": {"parts": [{"text": "overflowing garbage on the roadside"}]},
        "taskType": "RETRIEVAL_DOCUMENT",
        "title": "Sanitation issue",
        "outputDimensionality": 1536,
    }


def test_generate_embeddings_uses_batch_endpoint(monkeypatch):
    """Batch embedding requests use batchEmbedContents and preserve alignment."""
    monkeypatch.setattr(embedding_module.settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(embedding_module.httpx, "AsyncClient", _FakeAsyncClient)

    _FakeAsyncClient.requests = []
    _FakeAsyncClient.responses = [
        httpx.Response(
            200,
            json={
                "embeddings": [
                    {"values": [0.11, 0.22]},
                    {"values": [0.33, 0.44]},
                ]
            },
            request=httpx.Request(
                "POST",
                GeminiEmbeddingService._batch_embed_url("gemini-embedding-2-preview"),
            ),
        )
    ]

    result = asyncio.run(
        GeminiEmbeddingService.generate_embeddings(
            ["first issue description", "second issue description"],
            task_type="RETRIEVAL_DOCUMENT",
            titles=["Issue one", "Issue two"],
            output_dimensionality=256,
        )
    )

    assert result == [[0.11, 0.22], [0.33, 0.44]]
    assert _FakeAsyncClient.requests[0]["url"] == GeminiEmbeddingService._batch_embed_url(
        "gemini-embedding-2-preview"
    )
    assert _FakeAsyncClient.requests[0]["json"] == {
        "requests": [
            {
                "model": "models/gemini-embedding-2-preview",
                "content": {"parts": [{"text": "first issue description"}]},
                "taskType": "RETRIEVAL_DOCUMENT",
                "title": "Issue one",
                "outputDimensionality": 256,
            },
            {
                "model": "models/gemini-embedding-2-preview",
                "content": {"parts": [{"text": "second issue description"}]},
                "taskType": "RETRIEVAL_DOCUMENT",
                "title": "Issue two",
                "outputDimensionality": 256,
            },
        ]
    }


def test_generate_image_embedding_detects_mime_type_from_path(monkeypatch, tmp_path):
    """Image embeddings detect MIME type from the file extension."""
    monkeypatch.setattr(embedding_module.settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(embedding_module.httpx, "AsyncClient", _FakeAsyncClient)

    image_path = tmp_path / "issue-photo.png"
    image_bytes = b"fake-image-bytes"
    image_path.write_bytes(image_bytes)

    _FakeAsyncClient.requests = []
    _FakeAsyncClient.responses = [
        httpx.Response(
            200,
            json={"embedding": {"values": [0.5, 0.6]}},
            request=httpx.Request(
                "POST",
                GeminiEmbeddingService._embed_url("gemini-embedding-2-preview"),
            ),
        )
    ]

    result = asyncio.run(GeminiEmbeddingService.generate_image_embedding(str(image_path)))

    assert result == [0.5, 0.6]
    assert _FakeAsyncClient.requests[0]["json"] == {
        "model": "models/gemini-embedding-2-preview",
        "content": {
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64.b64encode(image_bytes).decode("utf-8"),
                    }
                }
            ]
        },
        "outputDimensionality": 1536,
    }


def test_generate_embedding_rejects_empty_text():
    """Blank text inputs are rejected before the provider call."""
    with pytest.raises(ValueError, match="must not be empty"):
        asyncio.run(GeminiEmbeddingService.generate_embedding("   "))


def test_generate_embeddings_requires_matching_titles_length():
    """Titles must align one-to-one with texts."""
    with pytest.raises(ValueError, match="Titles length must match texts length"):
        asyncio.run(
            GeminiEmbeddingService.generate_embeddings(
                ["first", "second"],
                titles=["only-one"],
            )
        )


def test_generate_embedding_surfaces_provider_error(monkeypatch):
    """Provider HTTP errors include Gemini's message details."""
    monkeypatch.setattr(embedding_module.settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(embedding_module.httpx, "AsyncClient", _FakeAsyncClient)

    _FakeAsyncClient.requests = []
    _FakeAsyncClient.responses = [
        httpx.Response(
            403,
            json={"error": {"message": "API key is invalid."}},
            request=httpx.Request(
                "POST",
                GeminiEmbeddingService._embed_url("gemini-embedding-2-preview"),
            ),
        )
    ]

    with pytest.raises(
        RuntimeError, match="Gemini embedding HTTP error: 403 - API key is invalid."
    ):
        asyncio.run(GeminiEmbeddingService.generate_embedding("blocked request"))
