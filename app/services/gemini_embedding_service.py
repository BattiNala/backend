# pylint: disable=too-many-arguments
"""Service for generating text and image embeddings using Gemini."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.core.constants import GEMINI_MAX_RETRIES, GEMINI_RETRYABLE_STATUS_CODES
from app.core.logger import get_logger

logger = get_logger(__name__)
GEMINI_EMBEDDING_TIMEOUT = httpx.Timeout(60.0, connect=10.0, read=60.0, write=20.0)


class GeminiEmbeddingService:
    """Wrapper around the Gemini Embeddings API."""

    @staticmethod
    def _headers() -> dict[str, str]:
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        return {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _embed_url(model: str) -> str:
        """Build the Gemini embedContent URL for a model name."""
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"

    @staticmethod
    def _batch_embed_url(model: str) -> str:
        """Build the Gemini batchEmbedContents URL for a model name."""
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"

    @staticmethod
    def _extract_http_error_message(response: httpx.Response) -> str | None:
        """Extract a readable provider error message from an error response."""
        try:
            payload = response.json()
        except (ValueError, TypeError):
            payload = None

        if isinstance(payload, dict):
            error_message = payload.get("error", {}).get("message")
            if isinstance(error_message, str) and error_message.strip():
                return error_message.strip()

        response_text = response.text.strip()
        if response_text:
            return response_text

        return None

    @staticmethod
    async def _post_with_retry(
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        json_payload: dict[str, Any],
    ) -> httpx.Response:
        """Retry transient Gemini HTTP failures with exponential backoff."""
        last_exc: httpx.HTTPStatusError | None = None

        for attempt in range(1, GEMINI_MAX_RETRIES + 1):
            response = await client.post(url, headers=headers, json=json_payload)

            try:
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in GEMINI_RETRYABLE_STATUS_CODES:
                    raise

                if attempt == GEMINI_MAX_RETRIES:
                    raise

                sleep_seconds = 0.5 * (2 ** (attempt - 1))
                logger.warning(
                    "Gemini embedding transient HTTP error %s on attempt %s/%s; retrying in %.2fs",
                    exc.response.status_code,
                    attempt,
                    GEMINI_MAX_RETRIES,
                    sleep_seconds,
                )
                await asyncio.sleep(sleep_seconds)

        if last_exc is not None:
            raise last_exc

        raise RuntimeError("Gemini embedding request failed before a response was received.")

    @staticmethod
    def _resolve_model(model: str | None) -> str:
        resolved = (model or settings.GEMINI_EMBEDDING_MODEL).strip()
        if not resolved:
            raise ValueError("Gemini embedding model must not be empty.")
        return resolved

    @staticmethod
    def _resolve_output_dimensionality(output_dimensionality: int | None) -> int:
        resolved = output_dimensionality or settings.GEMINI_EMBEDDING_DIMENSIONS
        if resolved <= 0:
            raise ValueError("Gemini embedding output dimensionality must be positive.")
        return resolved

    @staticmethod
    def _clean_text(text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Input text must not be empty.")
        return cleaned

    @staticmethod
    def _request_payload(
        *,
        model: str,
        parts: list[dict[str, Any]],
        task_type: str | None = None,
        title: str | None = None,
        output_dimensionality: int,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": f"models/{model}",
            "content": {
                "parts": parts,
            },
            "outputDimensionality": output_dimensionality,
        }

        if task_type:
            payload["taskType"] = task_type.strip()

        if title and title.strip():
            payload["title"] = title.strip()

        return payload

    @staticmethod
    def _text_part(text: str) -> dict[str, Any]:
        return {
            "text": text,
        }

    @staticmethod
    def _resolve_image_mime_type(image_path: str, mime_type: str | None = None) -> str:
        if mime_type and mime_type.strip():
            resolved = mime_type.strip()
        else:
            guessed_mime_type, _ = mimetypes.guess_type(image_path)
            resolved = guessed_mime_type or ""

        if not resolved.startswith("image/"):
            raise ValueError("Unable to determine a valid image MIME type from the file path.")

        return resolved

    @staticmethod
    def _image_inline_part(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
        if not image_bytes:
            raise ValueError("Image bytes must not be empty.")

        return {
            "inline_data": {
                "mime_type": mime_type,
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }
        }

    @staticmethod
    def _extract_embedding(data: dict[str, Any]) -> list[float]:
        """Extract a single embedding vector from Gemini response data."""
        values = data.get("embedding", {}).get("values")
        if not isinstance(values, list) or not values:
            raise ValueError("Gemini embedding response did not contain embedding values.")

        return [float(value) for value in values]

    @staticmethod
    def _extract_embeddings(data: dict[str, Any]) -> list[list[float]]:
        """Extract batch embedding vectors from Gemini response data."""
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or not embeddings:
            raise ValueError("Gemini batch embedding response did not contain embeddings.")

        vectors: list[list[float]] = []
        for embedding in embeddings:
            values = embedding.get("values") if isinstance(embedding, dict) else None
            if not isinstance(values, list) or not values:
                raise ValueError("Gemini batch embedding response contained an invalid vector.")
            vectors.append([float(value) for value in values])

        return vectors

    @classmethod
    async def generate_embedding(
        cls,
        text: str,
        *,
        task_type: str | None = None,
        title: str | None = None,
        output_dimensionality: int | None = None,
        model: str | None = None,
    ) -> list[float]:
        """Generate a single embedding vector for the provided text."""
        resolved_model = cls._resolve_model(model)
        resolved_output_dimensionality = cls._resolve_output_dimensionality(output_dimensionality)
        payload = cls._request_payload(
            model=resolved_model,
            parts=[cls._text_part(cls._clean_text(text))],
            task_type=task_type,
            title=title,
            output_dimensionality=resolved_output_dimensionality,
        )

        try:
            async with httpx.AsyncClient(timeout=GEMINI_EMBEDDING_TIMEOUT) as client:
                response = await cls._post_with_retry(
                    client=client,
                    url=cls._embed_url(resolved_model),
                    headers=cls._headers(),
                    json_payload=payload,
                )
            return cls._extract_embedding(response.json())
        except httpx.HTTPStatusError as exc:
            detail = cls._extract_http_error_message(exc.response)
            message = f"Gemini embedding HTTP error: {exc.response.status_code}"
            if detail:
                message = f"{message} - {detail}"
            raise RuntimeError(message) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Gemini embedding service is currently unavailable.") from exc

    @classmethod
    async def generate_embeddings(
        cls,
        texts: list[str],
        *,
        task_type: str | None = None,
        titles: list[str | None] | None = None,
        output_dimensionality: int | None = None,
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embedding vectors for multiple texts in a single API call."""
        if not texts:
            raise ValueError("At least one text input is required.")

        if titles is not None and len(titles) != len(texts):
            raise ValueError("Titles length must match texts length.")

        resolved_model = cls._resolve_model(model)
        resolved_output_dimensionality = cls._resolve_output_dimensionality(output_dimensionality)
        requests = [
            cls._request_payload(
                model=resolved_model,
                parts=[cls._text_part(cls._clean_text(text))],
                task_type=task_type,
                title=titles[index] if titles is not None else None,
                output_dimensionality=resolved_output_dimensionality,
            )
            for index, text in enumerate(texts)
        ]

        try:
            async with httpx.AsyncClient(timeout=GEMINI_EMBEDDING_TIMEOUT) as client:
                response = await cls._post_with_retry(
                    client=client,
                    url=cls._batch_embed_url(resolved_model),
                    headers=cls._headers(),
                    json_payload={"requests": requests},
                )
            return cls._extract_embeddings(response.json())
        except httpx.HTTPStatusError as exc:
            detail = cls._extract_http_error_message(exc.response)
            message = f"Gemini embedding HTTP error: {exc.response.status_code}"
            if detail:
                message = f"{message} - {detail}"
            raise RuntimeError(message) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Gemini embedding service is currently unavailable.") from exc

    @classmethod
    async def generate_image_embedding(
        cls,
        image_path: str,
        *,
        mime_type: str | None = None,
        output_dimensionality: int | None = None,
        model: str | None = None,
    ) -> list[float]:
        """Generate a single embedding vector for an image file."""
        resolved_model = cls._resolve_model(model)
        resolved_output_dimensionality = cls._resolve_output_dimensionality(output_dimensionality)
        resolved_mime_type = cls._resolve_image_mime_type(image_path, mime_type=mime_type)
        image_bytes = Path(image_path).read_bytes()
        payload = cls._request_payload(
            model=resolved_model,
            parts=[cls._image_inline_part(image_bytes, resolved_mime_type)],
            output_dimensionality=resolved_output_dimensionality,
        )

        try:
            async with httpx.AsyncClient(timeout=GEMINI_EMBEDDING_TIMEOUT) as client:
                response = await cls._post_with_retry(
                    client=client,
                    url=cls._embed_url(resolved_model),
                    headers=cls._headers(),
                    json_payload=payload,
                )
            return cls._extract_embedding(response.json())
        except httpx.HTTPStatusError as exc:
            detail = cls._extract_http_error_message(exc.response)
            message = f"Gemini embedding HTTP error: {exc.response.status_code}"
            if detail:
                message = f"{message} - {detail}"
            raise RuntimeError(message) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Gemini embedding service is currently unavailable.") from exc
