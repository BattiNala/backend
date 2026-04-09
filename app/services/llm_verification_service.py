# pylint: disable=too-few-public-methods,protected-access
"""Service for verifying issue report images using an LLM (Mistral,GROQ,GEMINI)."""

import asyncio
import base64
import json
import mimetypes
import os
from collections import deque
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.core.config import settings
from app.core.constants import (
    GEMINI_INLINE_IMAGE_MAX_BYTES,
    GEMINI_MAX_RETRIES,
    GEMINI_MODEL,
    GEMINI_RETRYABLE_STATUS_CODES,
    GEMINI_STRICT_MODEL,
    GEMINI_UPLOAD_START_URL,
    GROQ_API_URL,
    GROQ_MODEL,
    GROQ_STRICT_MODEL,
    IMAGE_VERIFICATION_SYSTEM_PROMPT,
    MISTRAL_API_URL,
    MISTRAL_MODEL,
    NORMALIZATION_PROMPT as normalization_prompt,
)
from app.core.logger import get_logger
from app.exceptions.task_exception import VerificationError
from app.schemas.llm_vadiation import (
    ImageVerificationResult,
    VerificationResponse,
    VerificationVerdict,
)
from app.utils.llm_utils import (
    build_image_verification_prompt,
    extract_json,
    image_verification_response_schema,
    normalize_result,
)

logger = get_logger(__name__)
HTTP_TIMEOUT = httpx.Timeout(60.0, connect=10.0, read=60.0, write=20.0)
GROQ_TIMEOUT = httpx.Timeout(60.0, connect=10.0, read=60.0, write=20.0)
GEMINI_TIMEOUT = httpx.Timeout(90.0, connect=15.0, read=90.0, write=30.0)


class AsyncMistralRateLimiter:  # pylint: disable=too-few-public-methods
    """Simple async in-process rolling-window rate limiter."""

    def __init__(self, max_requests: int = 100, time_window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.time_window_seconds = time_window_seconds
        self.requests: deque[datetime] = deque()
        self._lock = asyncio.Lock()

    async def wait_if_needed(self) -> None:
        """Wait if the rate limit has been reached, using a rolling time window."""
        async with self._lock:
            now = datetime.now()

            while self.requests and now - self.requests[0] >= timedelta(
                seconds=self.time_window_seconds
            ):
                self.requests.popleft()

            if len(self.requests) >= self.max_requests:
                sleep_time = (
                    self.time_window_seconds - (now - self.requests[0]).total_seconds() + 0.25
                )
                if sleep_time > 0:
                    logger.warning("Mistral rate limit reached; sleeping %.2f seconds", sleep_time)
                    await asyncio.sleep(sleep_time)

                now = datetime.now()
                while self.requests and now - self.requests[0] >= timedelta(
                    seconds=self.time_window_seconds
                ):
                    self.requests.popleft()

            self.requests.append(datetime.now())


rate_limiter = AsyncMistralRateLimiter()


class LLMVerificationService:
    """Service for verifying issue report images using an LLM (Mistral)."""

    _client: httpx.AsyncClient | None = None
    _client_lock = asyncio.Lock()

    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        """Get or create a shared AsyncClient instance for Mistral API calls."""
        if cls._client is None:
            async with cls._client_lock:
                if cls._client is None:
                    cls._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)
        return cls._client

    @classmethod
    async def close_client(cls) -> None:
        """Close the shared AsyncClient instance if it exists."""
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None

    @staticmethod
    def _headers() -> dict[str, str]:
        """Construct headers for Mistral API requests, including authorization."""
        api_key = getattr(settings, "MISTRAL_API_KEY", None)
        if not api_key:
            raise VerificationError("MISTRAL_API_KEY is not configured.")

        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _build_content(prompt: str, image_urls: list[str] | None) -> list[dict[str, Any]]:
        """
        Build the content array for the Mistral API request, including the prompt and image URLs.
        """
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        for image_url in image_urls or []:
            if image_url and image_url.strip():
                content.append(
                    {
                        "type": "image_url",
                        "image_url": image_url.strip(),
                    }
                )

        return content

    @staticmethod
    def _build_payload(
        prompt: str,
        image_urls: list[str] | None = None,
        max_tokens: int = 120,
    ) -> dict[str, Any]:
        """Construct the payload for the Mistral API request."""
        return {
            "model": MISTRAL_MODEL,
            "temperature": 0,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": IMAGE_VERIFICATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": LLMVerificationService._build_content(prompt, image_urls),
                },
            ],
        }

    @staticmethod
    def _extract_message_content(data: dict[str, Any]) -> str:
        """
        Extract the content from the Mistral API response,
        handling both string and structured formats.
        """
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise VerificationError("Invalid response format from Mistral.") from exc

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            joined = "".join(text_parts).strip()
            if joined:
                return joined

        raise VerificationError("Mistral response did not contain usable text.")

    @staticmethod
    def _fallback_result(message: str) -> VerificationResponse:
        """Construct a standardized fallback response when verification fails."""
        return VerificationResponse(
            ok=False,
            status="error",
            message=message,
            result=None,
        )

    @staticmethod
    async def verify_images(
        issue_type: str,
        issue_description: str,
        image_urls: list[str] | None = None,
        max_tokens: int = 120,
    ) -> VerificationResponse:
        """
        Main method to verify images using Mistral,
        with fallbacks to Gemini and Groq if Mistral fails.
        """
        mistral_response = await LLMVerificationService.verify_with_mistral(
            issue_type=issue_type,
            issue_description=issue_description,
            image_urls=image_urls,
            max_tokens=max_tokens,
        )

        if mistral_response.ok and mistral_response.result is not None:
            return mistral_response

        logger.warning(
            "Mistral failed; falling back to Gemini. status=%s message=%s",
            mistral_response.status,
            mistral_response.message,
        )

        groq_response = await GroqVerificationService.verify_with_groq(
            issue_type=issue_type,
            issue_description=issue_description,
            image_urls=image_urls,
            max_tokens=max_tokens,
        )

        if groq_response.ok and groq_response.result is not None:
            return groq_response

        gemini_response = await GeminiVerificationService.verify_with_gemini(
            issue_type=issue_type,
            issue_description=issue_description,
            image_urls=image_urls,
        )

        if gemini_response.ok and gemini_response.result is not None:
            return gemini_response

        logger.warning(
            "Gemini failed; falling back to Groq. status=%s message=%s",
            gemini_response.status,
            gemini_response.message,
        )

        return VerificationResponse(
            ok=False,
            status="error",
            message="All verification providers are currently unavailable.",
            result=None,
        )

    @staticmethod
    async def verify_with_mistral(
        issue_type: str,
        issue_description: str,
        image_urls: list[str] | None = None,
        max_tokens: int = 120,
    ) -> VerificationResponse:
        """Main method to verify images using Mistral LLM."""
        prompt = build_image_verification_prompt(
            issue_type=issue_type,
            issue_description=issue_description,
            image_count=len(image_urls or []),
        )

        cleaned_image_urls = [url.strip() for url in (image_urls or []) if url and url.strip()]

        if not cleaned_image_urls:
            return VerificationResponse(
                ok=True,
                status="success",
                result=ImageVerificationResult(
                    score=0,
                    verdict=VerificationVerdict.IRRELEVANT_OR_UNUSABLE,
                    rationale="No images were provided for verification.",
                ),
                message=None,
            )

        await rate_limiter.wait_if_needed()

        payload = LLMVerificationService._build_payload(
            prompt=prompt,
            image_urls=cleaned_image_urls,
            max_tokens=max_tokens,
        )

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.post(
                    MISTRAL_API_URL,
                    headers=LLMVerificationService._headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            raw_text = LLMVerificationService._extract_message_content(data)
            raw_json = extract_json(raw_text)
            result = normalize_result(raw_json)

            return VerificationResponse(
                ok=True,
                status="success",
                result=result,
                message=None,
            )

        except httpx.HTTPStatusError as exc:
            logger.exception("Mistral API returned non-2xx response: %s", exc.response.text)
            return LLMVerificationService._fallback_result(
                "Verification service returned an HTTP error."
            )
        except httpx.HTTPError as exc:
            logger.exception("HTTP error during Mistral API call: %s", exc)
            return LLMVerificationService._fallback_result(
                "Verification service is currently unavailable."
            )
        except VerificationError as exc:
            logger.exception("Verification parsing/validation error: %s", exc)
            return LLMVerificationService._fallback_result(str(exc))


class GroqVerificationService:
    """Service for verifying issue report images using Groq."""

    @staticmethod
    def _headers() -> dict[str, str]:
        api_key = getattr(settings, "GROQ_API_KEY", None)
        if not api_key:
            raise VerificationError("GROQ_API_KEY is not configured.")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _build_content(prompt: str, image_urls: list[str]) -> list[dict[str, Any]]:
        """Build OpenAI-compatible multimodal content for Groq chat completions."""
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        for image_url in image_urls:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                    },
                }
            )

        return content

    @staticmethod
    def _strict_response_format() -> dict[str, Any]:
        """Build a strict structured-output contract for Groq text normalization."""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "image_verification_result",
                "strict": True,
                "schema": image_verification_response_schema(),
            },
        }

    @staticmethod
    async def _normalize_with_groq_strict(
        raw_text: str,
        issue_type: str,
        issue_description: str,
        image_count: int,
        max_tokens: int,
    ) -> ImageVerificationResult:
        """Convert a non-schema Groq vision response into strict JSON using GPT-OSS."""

        payload = {
            "model": GROQ_STRICT_MODEL,
            "temperature": 0,
            "max_completion_tokens": max_tokens,
            "top_p": 1,
            "stream": False,
            "response_format": GroqVerificationService._strict_response_format(),
            "messages": [
                {"role": "system", "content": IMAGE_VERIFICATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": normalization_prompt.format(
                        issue_type=issue_type,
                        issue_description=issue_description,
                        image_count=image_count,
                        raw_text=raw_text,
                    ),
                },
            ],
        }

        async with httpx.AsyncClient(timeout=GROQ_TIMEOUT) as client:
            response = await client.post(
                GROQ_API_URL,
                headers=GroqVerificationService._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        normalized_text = LLMVerificationService._extract_message_content(data)
        return normalize_result(extract_json(normalized_text))

    @staticmethod
    async def verify_with_groq(
        issue_type: str,
        issue_description: str,
        image_urls: list[str] | None = None,
        max_tokens: int = 120,
    ) -> VerificationResponse:
        """Main method to verify images using Groq LLM, with strict normalization fallback."""
        prompt = build_image_verification_prompt(
            issue_type=issue_type,
            issue_description=issue_description,
            image_count=len(image_urls or []),
        )

        cleaned_image_urls = [u.strip() for u in (image_urls or []) if u and u.strip()]

        if not cleaned_image_urls:
            return VerificationResponse(
                ok=True,
                status="success",
                result=ImageVerificationResult(
                    score=0,
                    verdict=VerificationVerdict.IRRELEVANT_OR_UNUSABLE,
                    rationale="No images were provided for verification.",
                ),
                message=None,
            )

        payload = {
            "model": GROQ_MODEL,
            "temperature": 1e-8,
            "max_completion_tokens": max_tokens,
            "top_p": 1,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "image_verification_result",
                    "strict": False,
                    "schema": image_verification_response_schema(),
                },
            },
            "messages": [
                {"role": "system", "content": IMAGE_VERIFICATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": GroqVerificationService._build_content(prompt, cleaned_image_urls),
                },
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=GROQ_TIMEOUT) as client:
                response = await client.post(
                    GROQ_API_URL,
                    headers=GroqVerificationService._headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            raw_text = LLMVerificationService._extract_message_content(data)
            try:
                result = normalize_result(extract_json(raw_text))
            except VerificationError:
                logger.warning(
                    "Groq vision response was not schema-compliant; normalizing strictly"
                )
                result = await GroqVerificationService._normalize_with_groq_strict(
                    raw_text=raw_text,
                    issue_type=issue_type,
                    issue_description=issue_description,
                    image_count=len(cleaned_image_urls),
                    max_tokens=max_tokens,
                )

            return VerificationResponse(
                ok=True,
                status="success",
                result=result,
                message=None,
            )

        except httpx.HTTPStatusError as exc:
            logger.exception("Groq HTTP error %s: %s", exc.response.status_code, exc.response.text)
            detail = GeminiVerificationService.extract_http_error_message(exc.response)
            message = f"Groq HTTP error: {exc.response.status_code}"
            if detail:
                message = f"{message} - {detail}"
            return VerificationResponse(
                ok=False,
                status="error",
                message=message,
                result=None,
            )
        except httpx.HTTPError as exc:
            logger.exception("Groq transport error: %s", exc)
            return VerificationResponse(
                ok=False,
                status="error",
                message="Groq verification service is currently unavailable.",
                result=None,
            )
        except VerificationError as exc:
            logger.exception("Groq parsing/validation error: %s", exc)
            return VerificationResponse(
                ok=False,
                status="error",
                message="Groq returned an invalid response.",
                result=None,
            )


def gemini_generate_url(model: str) -> str:
    """Build the Gemini generateContent URL for a model name."""
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def gemini_generation_config(model: str) -> dict[str, Any]:
    """Build Gemini generation config tuned for structured verification output."""
    config: dict[str, Any] = {
        "temperature": 0,
        "responseMimeType": "application/json",
        "responseJsonSchema": image_verification_response_schema(),
    }

    if model.startswith("gemini-3"):
        config["thinkingConfig"] = {"thinkingLevel": "minimal"}
    elif model.startswith("gemini-2.5"):
        config["thinkingConfig"] = {"thinkingBudget": 0}

    return config


class GeminiVerificationService:
    """Service for verifying issue report images using Gemini."""

    @staticmethod
    def _headers() -> dict[str, str]:
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise VerificationError("GEMINI_API_KEY is not configured.")
        return {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }

    @staticmethod
    def extract_http_error_message(response: httpx.Response) -> str | None:
        """Extract a readable provider error message from a Gemini error response."""
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
    def extract_non_text_reason(data: dict[str, Any]) -> str | None:
        """Extract a human-readable reason when Gemini returns no text parts."""
        try:
            candidate = data["candidates"][0]
        except (KeyError, IndexError, TypeError):
            candidate = None

        reasons: list[str] = []
        if isinstance(candidate, dict):
            finish_reason = candidate.get("finishReason")
            if finish_reason:
                reasons.append(f"finishReason={finish_reason}")

            safety_ratings = candidate.get("safetyRatings")
            if isinstance(safety_ratings, list) and safety_ratings:
                reasons.append(f"safetyRatings={json.dumps(safety_ratings)}")

        prompt_feedback = data.get("promptFeedback")
        if prompt_feedback:
            reasons.append(f"promptFeedback={json.dumps(prompt_feedback)}")

        return "; ".join(reasons) if reasons else None

    @staticmethod
    def _extract_response_text(data: dict[str, Any]) -> str:
        """Extract text content from a Gemini generateContent response."""
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as exc:
            reason = GeminiVerificationService.extract_non_text_reason(data)
            if reason:
                raise VerificationError(f"Gemini returned no text content: {reason}") from exc
            raise VerificationError("Invalid response format from Gemini.") from exc

        text_parts: list[str] = []
        for part in parts:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text)

        joined = "".join(text_parts).strip()
        if joined:
            return joined

        reason = GeminiVerificationService.extract_non_text_reason(data)
        if reason:
            raise VerificationError(f"Gemini response did not contain usable text: {reason}")

        raise VerificationError("Gemini response did not contain usable text.")

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
                    "Gemini transient HTTP error %s on attempt %s/%s; retrying in %.2fs",
                    exc.response.status_code,
                    attempt,
                    GEMINI_MAX_RETRIES,
                    sleep_seconds,
                )
                await asyncio.sleep(sleep_seconds)

        if last_exc is not None:
            raise last_exc

        raise VerificationError("Gemini request failed before a response was received.")

    @staticmethod
    async def _normalize_with_gemini_strict(
        raw_text: str,
        issue_type: str,
        issue_description: str,
        image_count: int,
    ) -> ImageVerificationResult:
        """Convert a non-schema Gemini vision response into strict JSON."""

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": normalization_prompt.format(
                                issue_type=issue_type,
                                issue_description=issue_description,
                                image_count=image_count,
                                raw_text=raw_text,
                            )
                        }
                    ]
                }
            ],
            "generationConfig": gemini_generation_config(GEMINI_STRICT_MODEL),
        }

        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
            print(f"Sending normalization request to {GEMINI_STRICT_MODEL} with payload:", payload)
            response = await GeminiVerificationService._post_with_retry(
                client=client,
                url=gemini_generate_url(GEMINI_STRICT_MODEL),
                headers=GeminiVerificationService._headers(),
                json_payload=payload,
            )
            data = response.json()

        normalized_text = GeminiVerificationService._extract_response_text(data)
        normalized_json = extract_json(normalized_text)
        return normalize_result(normalized_json)

    @staticmethod
    async def _download_image(
        client: httpx.AsyncClient,
        image_url: str,
    ) -> tuple[bytes, str, str]:
        response = await client.get(image_url, follow_redirects=True)
        response.raise_for_status()

        content = response.content
        mime_type = response.headers.get("content-type", "").split(";")[0].strip()
        if not mime_type.startswith("image/"):
            mime_type = "image/jpeg"

        filename = os.path.basename(image_url.split("?")[0]) or "image"
        if "." not in filename:
            ext = mimetypes.guess_extension(mime_type) or ".jpg"
            filename = f"{filename}{ext}"

        return content, mime_type, filename

    @staticmethod
    async def _upload_file_to_gemini(
        client: httpx.AsyncClient,
        data: bytes,
        mime_type: str,
        display_name: str,
    ) -> str:
        start_headers = {
            "x-goog-api-key": GeminiVerificationService._headers()["x-goog-api-key"],
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(len(data)),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        }

        start_resp = await client.post(
            GEMINI_UPLOAD_START_URL,
            headers=start_headers,
            json={"file": {"display_name": display_name}},
        )
        start_resp.raise_for_status()

        upload_url = start_resp.headers.get("x-goog-upload-url")
        if not upload_url:
            raise VerificationError("Gemini upload URL missing from response.")

        upload_headers = {
            "Content-Length": str(len(data)),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        }

        upload_resp = await client.post(
            upload_url,
            headers=upload_headers,
            content=data,
        )
        upload_resp.raise_for_status()

        payload = upload_resp.json()
        file_uri = payload.get("file", {}).get("uri")
        if not file_uri:
            raise VerificationError("Gemini file URI missing from upload response.")

        return file_uri

    @staticmethod
    async def _image_to_part(
        client: httpx.AsyncClient,
        image_url: str,
        index: int,
        force_upload: bool = False,
    ) -> dict[str, Any]:
        """Convert an image URL into a Gemini content part, uploading if too large."""
        data, mime_type, filename = await GeminiVerificationService._download_image(
            client, image_url
        )

        should_upload = force_upload or len(data) > GEMINI_INLINE_IMAGE_MAX_BYTES

        if should_upload:
            file_uri = await GeminiVerificationService._upload_file_to_gemini(
                client=client,
                data=data,
                mime_type=mime_type,
                display_name=f"issue_image_{index}_{filename}",
            )
            return {
                "file_data": {
                    "mime_type": mime_type,
                    "file_uri": file_uri,
                }
            }

        encoded = base64.b64encode(data).decode("utf-8")
        return {
            "inline_data": {
                "mime_type": mime_type,
                "data": encoded,
            }
        }

    @staticmethod
    async def _build_parts(
        prompt: str,
        image_urls: list[str],
    ) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = [{"text": prompt}]

        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
            for idx, image_url in enumerate(image_urls, start=1):
                parts.append(
                    await GeminiVerificationService._image_to_part(
                        client=client,
                        image_url=image_url,
                        index=idx,
                        force_upload=False,
                    )
                )

        return parts

    @staticmethod
    async def verify_with_gemini(
        issue_type: str,
        issue_description: str,
        image_urls: list[str] | None = None,
    ) -> VerificationResponse:
        """Main method to verify images using Gemini LLM, with strict normalization fallback."""
        prompt = build_image_verification_prompt(
            issue_type=issue_type,
            issue_description=issue_description,
            image_count=len(image_urls or []),
        )

        cleaned_image_urls = [u.strip() for u in (image_urls or []) if u and u.strip()]

        if not cleaned_image_urls:
            return VerificationResponse(
                ok=True,
                status="success",
                result=ImageVerificationResult(
                    score=0,
                    verdict=VerificationVerdict.IRRELEVANT_OR_UNUSABLE,
                    rationale="No images were provided for verification.",
                ),
                message=None,
            )

        try:
            parts = await GeminiVerificationService._build_parts(prompt, cleaned_image_urls)

            payload = {
                "contents": [
                    {
                        "parts": parts,
                    }
                ],
                "generationConfig": gemini_generation_config(GEMINI_MODEL),
            }

            async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
                response = await GeminiVerificationService._post_with_retry(
                    client=client,
                    url=gemini_generate_url(GEMINI_MODEL),
                    headers=GeminiVerificationService._headers(),
                    json_payload=payload,
                )
                data = response.json()

            raw_text = GeminiVerificationService._extract_response_text(data)
            try:
                result = normalize_result(extract_json(raw_text))
            except VerificationError:
                logger.warning(
                    "Gemini vision response was not schema-compliant; normalizing strictly."
                )
                result = await GeminiVerificationService._normalize_with_gemini_strict(
                    raw_text=raw_text,
                    issue_type=issue_type,
                    issue_description=issue_description,
                    image_count=len(cleaned_image_urls),
                )

            return VerificationResponse(
                ok=True,
                status="success",
                result=result,
                message=None,
            )

        except httpx.HTTPStatusError as exc:
            logger.exception(
                "Gemini HTTP error %s: %s", exc.response.status_code, exc.response.text
            )
            detail = GeminiVerificationService.extract_http_error_message(exc.response)
            message = f"Gemini HTTP error: {exc.response.status_code}"
            if detail:
                message = f"{message} - {detail}"
            return VerificationResponse(
                ok=False,
                status="error",
                message=message,
                result=None,
            )
        except httpx.HTTPError as exc:
            logger.exception("Gemini transport error: %s", exc)
            return VerificationResponse(
                ok=False,
                status="error",
                message="Gemini verification service is currently unavailable.",
                result=None,
            )
        except (KeyError, IndexError, TypeError, ValueError, VerificationError) as exc:
            logger.exception("Gemini parsing/validation error: %s", exc)
            return VerificationResponse(
                ok=False,
                status="error",
                message=str(exc),
                result=None,
            )
