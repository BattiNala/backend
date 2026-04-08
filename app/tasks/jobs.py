"""
Job utilities for the application.
"""

from app.core.logger import get_logger
from app.db.session import AsyncSessionLocal
from app.models.issue import Issue
from app.repositories.issue_repo import IssueRepository
from app.schemas.issue import IssueStatus
from app.services.llm_verification_service import (
    VerificationResponse,
    should_auto_accept,
    should_reject,
)
from app.tasks.image_jobs import check_duplicate_using_phash
from app.tasks.llm_verify_job import llm_verify
from app.utils.s3_utils import return_attachment_urls

logger = get_logger("tasks.jobs")


async def validate_issue_images(issue_repo: IssueRepository, new_issue: Issue | None) -> str | None:
    """Validate the image associated with an issue."""
    if not new_issue:
        return None

    urls = return_attachment_urls(new_issue)
    res: VerificationResponse | None = await llm_verify(
        new_issue.department.department_name, new_issue.description, image_urls=urls
    )
    if not res:
        logger.warning(
            "LLM verification failed for issue_id=%s, skipping validation",
            new_issue.issue_id,
        )
        return None

    if should_auto_accept(res.result):
        return "accepted"

    if should_reject(res.result):
        reason = (
            "Rejected by LLM" + res.result.rationale
            if res.result.rationale
            else "LLM verification failed"
        )
        await issue_repo.reject_issue(new_issue, reason=reason, auto_reject=True)
        return "rejected"

    await issue_repo.update_issue_status(new_issue, status=IssueStatus.PENDING_VERIFICATION)
    return "manual_review"


async def process_issue(issue_id: int) -> None:
    """Process a new issue by validating its images and checking for duplicates."""
    async with AsyncSessionLocal() as db:
        try:
            issue_repo = IssueRepository(db)
            new_issue = await issue_repo.get_issue_by_id(issue_id)
            status = await validate_issue_images(issue_repo, new_issue)
            if status is None or status == "accepted":
                await check_duplicate_using_phash(db, new_issue)
            await db.commit()

        except Exception:
            await db.rollback()
            raise
