"""Service for verifying issue report images using an LLM (Mistral)."""

import asyncio
import json
import logging
import re
from collections import deque
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.config import settings
from app.exceptions.task_exception import VerificationError

logger = logging.getLogger(__name__)

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = getattr(settings, "MISTRAL_MODEL", "mistral-large-latest")
HTTP_TIMEOUT = httpx.Timeout(60.0, connect=10.0, read=60.0, write=20.0)


IMAGE_VERIFICATION_SYSTEM_PROMPT = """
You are an image-verification assistant for a user-submitted issue reporting system.

Your task is to assess whether the provided image(s) are relevant and plausibly supportive of
the reported issue.

Important constraints:
- Do NOT claim certainty about real-world authenticity.
- You are NOT doing forensic image authentication.
- Judge only from the visible image content and the issue report details.
- Be conservative when evidence is weak, ambiguous, low quality, or missing.
- Penalize images that are generic, unrelated, stock-like, duplicated, overly blurry, or
 inconsistent with the report.
- Reward images that clearly depict the reported issue, context, and visible supporting details.
- If no images are provided, score very low.
- Output must be valid JSON only.
""".strip()


def build_image_verification_prompt(
    issue_type: str,
    issue_description: str,
    image_count: int,
) -> str:
    """
    Construct a prompt for the LLM to evaluate the relevance and supportiveness of attached images
    for a user-submitted issue report.
    """
    return f"""
Evaluate the attached image(s) for a user-submitted issue report.

Issue type: {issue_type}
Issue description: {issue_description}
Number of attached images: {image_count}

Scoring rubric:
- 90-100: Images are highly relevant and strongly support the reported issue.
- 70-89: Images are relevant and reasonably support the issue, with minor ambiguity.
- 40-69: Images are somewhat relevant but weak, incomplete, generic, or unclear.
- 10-39: Images are minimally relevant, suspiciously generic, or poorly matched to the report.
- 0-9: Images are missing, clearly irrelevant, or unusable.

Evaluate:
1. Relevance to the reported issue
2. Visual consistency with the description
3. Clarity and usefulness of the evidence
4. Signs the image may be generic, misleading, staged, duplicated, or low-value evidence

Return valid JSON with exactly these fields:
{{
  "score": <integer 0 to 100>,
  "verdict": "<one of: strong_match, moderate_match, weak_match, irrelevant_or_unusable>",
  "rationale": "<short explanation, max 40 words>"
}}
""".strip()


class VerificationVerdict(StrEnum):  # pylint: disable=too-few-public-methods
    """Verdict categories for image verification results."""

    STRONG_MATCH = "strong_match"
    MODERATE_MATCH = "moderate_match"
    WEAK_MATCH = "weak_match"
    IRRELEVANT_OR_UNUSABLE = "irrelevant_or_unusable"


class ImageVerificationResult(BaseModel):  # pylint: disable=too-few-public-methods
    """Structured result from LLM image verification."""

    score: int = Field(ge=0, le=100)
    verdict: VerificationVerdict
    rationale: str = Field(min_length=1, max_length=240)

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str) -> str:
        """Clean and validate the rationale text, ensuring it's not empty and is concise."""
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("rationale cannot be empty")

        words = cleaned.split()
        if len(words) > 40:
            cleaned = " ".join(words[:40])

        return cleaned


class VerificationResponse(BaseModel):  # pylint: disable=too-few-public-methods
    """Standardized response for image verification attempts."""

    ok: bool
    result: ImageVerificationResult | None = None
    status: str
    message: str | None = None


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
    def _extract_json(text: str) -> dict[str, Any]:
        """Attempt to parse JSON from the provided text, with fallback strategies."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise VerificationError("Model did not return valid JSON.") from None

            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise VerificationError("Unable to parse JSON from model response.") from exc

    @staticmethod
    def _normalize_result(raw: dict[str, Any]) -> ImageVerificationResult:
        """Validate and normalize the raw JSON into an ImageVerificationResult."""
        try:
            return ImageVerificationResult.model_validate(raw)
        except ValidationError as exc:
            raise VerificationError(f"Model JSON failed validation: {exc}") from exc

    @staticmethod
    def _fallback_result(message: str) -> VerificationResponse:
        return VerificationResponse(
            ok=False,
            status="error",
            message=message,
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
            raw_json = LLMVerificationService._extract_json(raw_text)
            result = LLMVerificationService._normalize_result(raw_json)

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


def should_auto_accept(result: ImageVerificationResult) -> bool:
    """Determine if the result meets criteria for automatic acceptance."""
    return result.verdict == VerificationVerdict.STRONG_MATCH and result.score >= 85


def should_send_to_manual_review(result: ImageVerificationResult) -> bool:
    """Determine if the result should be sent for manual review."""
    return (
        result.verdict
        in {
            VerificationVerdict.MODERATE_MATCH,
            VerificationVerdict.WEAK_MATCH,
        }
        or 40 <= result.score < 85
    )


def should_reject(result: ImageVerificationResult) -> bool:
    """Determine if the result should be rejected."""
    return result.verdict == VerificationVerdict.IRRELEVANT_OR_UNUSABLE or result.score < 40


def derive_review_decision(result: ImageVerificationResult) -> str:
    """Derive a high-level review decision based on the verification result."""
    if should_auto_accept(result):
        return "accepted"
    if should_reject(result):
        return "rejected"
    return "manual_review"
