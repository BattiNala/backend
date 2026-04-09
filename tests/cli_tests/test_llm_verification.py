"""CLI smoke test for all LLM verification providers."""

import asyncio
import os

from app.core.config import settings
from app.services.llm_verification_service import (
    GeminiVerificationService,
    GroqVerificationService,
    LLMVerificationService,
)


def _has_real_key(setting_name: str) -> bool:
    """Return True when a provider API key is configured for live calls."""
    value: str | None = getattr(settings, setting_name, None)
    return bool(value and value != "api-key-placeholder")


def _print_result(label, result):
    """Print a provider result in a readable format."""
    print(f"\n== {label} ==")
    print("ok:", result.ok)
    print("status:", result.status)
    print("message:", result.message)
    print("result:", result.result.model_dump() if result.result else None)


async def run_smoke_test():
    """Run each provider and the full fallback chain against a real image URL."""
    image_url = os.environ.get("LLM_TEST_IMAGE_URL")
    if not image_url:
        raise RuntimeError("Set LLM_TEST_IMAGE_URL to a reachable image URL before running.")

    issue_type = os.environ.get("LLM_TEST_ISSUE_TYPE", "Garbage")
    issue_description = os.environ.get(
        "LLM_TEST_ISSUE_DESCRIPTION",
        "Overflowing garbage near the roadside",
    )

    image_urls = [image_url]

    if _has_real_key("MISTRAL_API_KEY"):
        mistral_result = await LLMVerificationService.verify_with_mistral(
            issue_type=issue_type,
            issue_description=issue_description,
            image_urls=image_urls,
        )
        _print_result("Mistral", mistral_result)
    else:
        print("\n== Mistral ==")
        print("skipped: MISTRAL_API_KEY is not configured")

    if _has_real_key("GEMINI_API_KEY"):
        gemini_result = await GeminiVerificationService.verify_with_gemini(
            issue_type=issue_type,
            issue_description=issue_description,
            image_urls=image_urls,
        )
        _print_result("Gemini", gemini_result)
    else:
        print("\n== Gemini ==")
        print("skipped: GEMINI_API_KEY is not configured")

    if _has_real_key("GROQ_API_KEY"):
        groq_result = await GroqVerificationService.verify_with_groq(
            issue_type=issue_type,
            issue_description=issue_description,
            image_urls=image_urls,
        )
        _print_result("Groq", groq_result)
    else:
        print("\n== Groq ==")
        print("skipped: GROQ_API_KEY is not configured")

    fallback_result = await LLMVerificationService.verify_images(
        issue_type=issue_type,
        issue_description=issue_description,
        image_urls=image_urls,
    )
    _print_result("Full Fallback Chain", fallback_result)


asyncio.run(run_smoke_test())
