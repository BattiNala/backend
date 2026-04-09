# pylint: disable=too-few-public-methods
"""Schemas for validating and structuring LLM image verification results."""

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class VerificationVerdict(StrEnum):
    """Verdict categories for image verification results."""

    STRONG_MATCH = "strong_match"
    MODERATE_MATCH = "moderate_match"
    WEAK_MATCH = "weak_match"
    IRRELEVANT_OR_UNUSABLE = "irrelevant_or_unusable"


class ImageVerificationResult(BaseModel):
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


class VerificationResponse(BaseModel):
    """Standardized response for image verification attempts."""

    ok: bool
    result: ImageVerificationResult | None = None
    status: str
    message: str | None = None
