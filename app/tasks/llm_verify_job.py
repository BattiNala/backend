"""Celery task for verifying issue reports using an LLM (Mistral)."""

from typing import Optional

from app.core.logger import get_logger
from app.services.llm_verification_service import (
    LLMVerificationService,
    VerificationResponse,
    derive_review_decision,
)

logger = get_logger("tasks.jobs")


async def llm_verify(
    issue_type: str, issue_description: str, image_urls: list[str]
) -> Optional[VerificationResponse]:
    """Verify the issue using LLM inside a Celery worker."""

    res = await LLMVerificationService.verify_with_mistral(
        issue_type=issue_type,
        issue_description=issue_description,
        image_urls=image_urls,
    )

    if res.ok and res.result:
        decision = derive_review_decision(res.result)

        logger.info(
            "LLM verification successful: issue_type=%s score=%s verdict=%s decision=%s",
            issue_type,
            res.result.score,
            res.result.verdict,
            decision,
        )
        return res

    logger.error(
        "LLM verification failed: issue_type=%s error=%s",
        issue_type,
        res.message,
    )
    return None
