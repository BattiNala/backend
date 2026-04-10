"""Utility functions for deriving review decisions from image verification results."""

from app.utils.llm_utils import ImageVerificationResult, VerificationVerdict


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
