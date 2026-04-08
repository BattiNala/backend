"""Background tasks related to image processing and validation for issue reports."""

from app.core.logger import get_logger
from app.models.attachment import Attachment
from app.models.issue import Issue
from app.repositories.issue_repo import IssueRepository
from app.schemas.issue import IssueStatus
from app.services.issue_image_validation_service import IssueImageValidationService
from app.services.issue_proximity_service import IssueProximityService
from app.tasks.task_assign_job import assign_issue_to_nearest_employee

logger = get_logger("tasks.image_jobs")


async def check_duplicate_using_phash(db, new_issue: Issue) -> None:
    """Validate issue for duplicates using pHash."""
    issue_repo = IssueRepository(db)

    nearby_issues = await IssueProximityService.get_nearby_candidate_issues(
        db=db,
        issue=new_issue,
        radius_meters=30.0,
    )

    if not nearby_issues:
        new_issue.status = IssueStatus.OPEN
        return

    best_match = None
    best_distance = 999

    # Compare attachment hashes
    for candidate in nearby_issues:
        new_attachment: Attachment
        old_attachment: Attachment
        for new_attachment in new_issue.attachments:
            if not new_attachment.phash:
                continue

            for old_attachment in candidate.attachments:
                if not old_attachment.phash:
                    continue

                distance = IssueImageValidationService.phash_distance(
                    new_attachment.phash,
                    old_attachment.phash,
                )

                if distance < best_distance:
                    best_distance = distance
                    best_match = candidate

    #  Decision logic
    if best_match:
        if best_distance <= 3:
            # strong duplicate
            new_issue.status = IssueStatus.REJECTED
            new_issue.duplicate_of_issue_id = best_match.issue_id
            logger.info(
                "Issue %s (%s) rejected as duplicate of issue %s (%s) with pHash distance %s",
                new_issue.issue_id,
                new_issue.issue_label,
                best_match.issue_id,
                best_match.issue_label,
                best_distance,
            )
            await issue_repo.reject_issue(
                new_issue,
                reason=f"Duplicate issue detected with issue of label {best_match.issue_label}",
                auto_reject=True,
            )
            return
        if best_distance <= 8:
            orb_result = await get_best_orb_match_between_issues(new_issue, best_match)
            if (
                orb_result
                and orb_result["good_matches"] >= 20
                and orb_result["similarity_score"] >= 0.15
            ):
                new_issue.status = IssueStatus.REJECTED
                new_issue.duplicate_of_issue_id = best_match.issue_id
                reason = (
                    f"Duplicate issue detected with issue of label {best_match.issue_label}"
                    f" based on pHash distance {best_distance} and ORB similarity score "
                    f"{orb_result['similarity_score']}"
                )
                logger.info("Issue Rejected as duplicate: %s", reason)
                await issue_repo.reject_issue(
                    new_issue,
                    reason=reason,
                    auto_reject=True,
                )
                return

        else:
            new_issue.status = IssueStatus.OPEN

    # No duplicate
    new_issue.status = IssueStatus.OPEN
    await assign_issue_to_nearest_employee(issue_id=new_issue.issue_id)


async def get_best_orb_match_between_issues(
    new_issue: Issue,
    candidate_issue: Issue,
) -> dict | None:
    """Compute the best ORB similarity match between attachments of two issues."""
    best_result = None
    new_attachment: Attachment
    old_attachment: Attachment
    for new_attachment in new_issue.attachments:
        for old_attachment in candidate_issue.attachments:
            if not new_attachment.path or not old_attachment.path:
                continue

            result = IssueImageValidationService.compute_orb_similarity(
                new_attachment.path,
                old_attachment.path,
            )

            if best_result is None:
                best_result = {
                    "new_attachment_id": new_attachment.attachment_id,
                    "old_attachment_id": old_attachment.attachment_id,
                    "good_matches": result["good_matches"],
                    "similarity_score": result["similarity_score"],
                }
                continue

            if result["good_matches"] > best_result["good_matches"]:
                best_result = {
                    "new_attachment_id": new_attachment.attachment_id,
                    "old_attachment_id": old_attachment.attachment_id,
                    "good_matches": result["good_matches"],
                    "similarity_score": result["similarity_score"],
                }

    return best_result
