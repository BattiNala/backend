"""Background tasks related to image processing and validation for issue reports."""

from pathlib import Path
from typing import TypedDict

from app.core.logger import get_logger
from app.models.attachment import Attachment
from app.models.issue import Issue
from app.repositories.issue_repo import IssueRepository
from app.schemas.issue import IssueStatus
from app.services.issue_image_validation_service import IssueImageValidationService
from app.services.issue_proximity_service import IssueProximityService
from app.tasks.task_assign_job import assign_issue_to_nearest_employee
from app.utils.s3_utils import delete_temp_files, download_s3_object_to_tempfile

logger = get_logger("tasks.image_jobs")

ORB_MIN_GOOD_MATCHES = 20
ORB_MIN_SIMILARITY_SCORE = 0.15
HISTOGRAM_COSINE_MIN_SIMILARITY_SCORE = 0.55
EMBEDDING_COSINE_MIN_SIMILARITY_SCORE = 0.55
PHASH_STRONG_DUPLICATE_DISTANCE = 3


class OrbMatchResult(TypedDict):
    """Best ORB match metadata for a pair of attachments."""

    new_attachment_id: int
    old_attachment_id: int
    good_matches: int
    similarity_score: float


class CosineMatchResult(TypedDict):
    """Best cosine match metadata for a pair of attachments."""

    new_attachment_id: int
    old_attachment_id: int
    similarity_score: float


class EmbeddingCosineMatchResult(TypedDict):
    """Best embedding cosine match metadata for a pair of attachments."""

    new_attachment_id: int
    old_attachment_id: int
    similarity_score: float


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

    best_match, best_distance = _find_best_phash_match(new_issue, nearby_issues)
    if best_match is None:
        new_issue.status = IssueStatus.OPEN
        await assign_issue_to_nearest_employee(issue_id=new_issue.issue_id)
        return

    if best_distance <= PHASH_STRONG_DUPLICATE_DISTANCE:
        await _reject_strong_duplicate(issue_repo, new_issue, best_match, best_distance)
        return

    if await _reject_similarity_duplicate(issue_repo, new_issue, best_match, best_distance):
        return

    # No duplicate
    new_issue.status = IssueStatus.OPEN
    await assign_issue_to_nearest_employee(issue_id=new_issue.issue_id)


def _find_best_phash_match(
    new_issue: Issue,
    nearby_issues: list[Issue],
) -> tuple[Issue | None, int]:
    """Return the closest nearby issue by pHash distance."""
    best_match: Issue | None = None
    best_distance = 999

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

    return best_match, best_distance


async def _reject_strong_duplicate(
    issue_repo: IssueRepository,
    new_issue: Issue,
    best_match: Issue,
    best_distance: int,
) -> None:
    """Reject a strong duplicate detected by pHash alone."""
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


async def _reject_similarity_duplicate(
    issue_repo: IssueRepository,
    new_issue: Issue,
    best_match: Issue,
    best_distance: int,
) -> bool:
    """Reject a duplicate when the pHash match needs a secondary image check."""
    orb_result = await get_best_orb_match_between_issues(new_issue, best_match)
    if (
        orb_result
        and orb_result["good_matches"] >= ORB_MIN_GOOD_MATCHES
        and orb_result["similarity_score"] >= ORB_MIN_SIMILARITY_SCORE
    ):
        reason = (
            f"Duplicate issue detected with issue of label {best_match.issue_label}"
            f" based on pHash distance {best_distance} and ORB similarity score "
            f"{orb_result['similarity_score']}"
        )
        await _reject_duplicate_issue(issue_repo, new_issue, best_match, reason)
        return True

    cosine_result = await get_best_cosine_match_between_issues(new_issue, best_match)
    if cosine_result and cosine_result["similarity_score"] >= HISTOGRAM_COSINE_MIN_SIMILARITY_SCORE:
        reason = (
            f"Duplicate issue detected with issue of label {best_match.issue_label}"
            f" based on pHash distance {best_distance} and cosine similarity score "
            f"{cosine_result['similarity_score']}"
        )
        await _reject_duplicate_issue(issue_repo, new_issue, best_match, reason)
        return True

    embedding_result = await get_best_embedding_cosine_match_between_issues(new_issue, best_match)
    if (
        embedding_result
        and embedding_result["similarity_score"] >= EMBEDDING_COSINE_MIN_SIMILARITY_SCORE
    ):
        reason = (
            f"Duplicate issue detected with issue of label {best_match.issue_label}"
            f" based on pHash distance {best_distance} and embedding cosine similarity score "
            f"{embedding_result['similarity_score']}"
        )
        await _reject_duplicate_issue(issue_repo, new_issue, best_match, reason)
        return True

    return False


async def _reject_duplicate_issue(
    issue_repo: IssueRepository,
    new_issue: Issue,
    best_match: Issue,
    reason: str,
) -> None:
    """Persist a duplicate rejection."""
    new_issue.status = IssueStatus.REJECTED
    new_issue.duplicate_of_issue_id = best_match.issue_id
    logger.info("Issue Rejected as duplicate: %s", reason)
    await issue_repo.reject_issue(new_issue, reason=reason, auto_reject=True)


async def get_best_orb_match_between_issues(
    new_issue: Issue,
    candidate_issue: Issue,
) -> OrbMatchResult | None:
    """Compute the best ORB similarity match between attachments of two issues."""
    best_result: OrbMatchResult | None = None
    best_good_matches = -1
    new_local_paths, new_temp_paths = await _materialize_attachment_paths(new_issue.attachments)
    old_local_paths, old_temp_paths = await _materialize_attachment_paths(
        candidate_issue.attachments
    )

    try:
        new_attachment: Attachment
        old_attachment: Attachment
        for new_attachment in new_issue.attachments:
            new_local_path = new_local_paths.get(id(new_attachment))
            if not new_local_path:
                continue

            for old_attachment in candidate_issue.attachments:
                old_local_path = old_local_paths.get(id(old_attachment))
                if not old_local_path:
                    continue

                result = IssueImageValidationService.compute_orb_similarity(
                    new_local_path,
                    old_local_path,
                )

                if result["good_matches"] > best_good_matches:
                    best_good_matches = result["good_matches"]
                    best_result = {
                        "new_attachment_id": new_attachment.attachment_id,
                        "old_attachment_id": old_attachment.attachment_id,
                        "good_matches": result["good_matches"],
                        "similarity_score": result["similarity_score"],
                    }
    finally:
        await delete_temp_files(new_temp_paths + old_temp_paths)

    return best_result


async def get_best_cosine_match_between_issues(
    new_issue: Issue,
    candidate_issue: Issue,
) -> CosineMatchResult | None:
    """Compute the best cosine similarity match between attachments of two issues."""
    best_result: CosineMatchResult | None = None
    best_similarity_score = float("-inf")
    new_local_paths, new_temp_paths = await _materialize_attachment_paths(new_issue.attachments)
    old_local_paths, old_temp_paths = await _materialize_attachment_paths(
        candidate_issue.attachments
    )

    try:
        new_attachment: Attachment
        old_attachment: Attachment
        for new_attachment in new_issue.attachments:
            new_local_path = new_local_paths.get(id(new_attachment))
            if not new_local_path:
                continue

            for old_attachment in candidate_issue.attachments:
                old_local_path = old_local_paths.get(id(old_attachment))
                if not old_local_path:
                    continue

                result = IssueImageValidationService.compute_cosine_similarity(
                    new_local_path,
                    old_local_path,
                )

                if result["similarity_score"] > best_similarity_score:
                    best_similarity_score = result["similarity_score"]
                    best_result = {
                        "new_attachment_id": new_attachment.attachment_id,
                        "old_attachment_id": old_attachment.attachment_id,
                        "similarity_score": result["similarity_score"],
                    }
    finally:
        await delete_temp_files(new_temp_paths + old_temp_paths)

    return best_result


async def get_best_embedding_cosine_match_between_issues(
    new_issue: Issue,
    candidate_issue: Issue,
) -> EmbeddingCosineMatchResult | None:
    """Compute the best cosine similarity match between attachment embeddings."""
    best_result: EmbeddingCosineMatchResult | None = None
    best_similarity_score = float("-inf")

    new_attachment: Attachment
    old_attachment: Attachment
    for new_attachment in new_issue.attachments:
        new_embedding = getattr(new_attachment, "embedding", None)
        if new_embedding is None:
            continue

        for old_attachment in candidate_issue.attachments:
            old_embedding = getattr(old_attachment, "embedding", None)
            if old_embedding is None:
                continue

            result = IssueImageValidationService.compute_embedding_cosine_similarity(
                new_embedding,
                old_embedding,
            )

            if result["similarity_score"] > best_similarity_score:
                best_similarity_score = result["similarity_score"]
                best_result = {
                    "new_attachment_id": new_attachment.attachment_id,
                    "old_attachment_id": old_attachment.attachment_id,
                    "similarity_score": result["similarity_score"],
                }

    return best_result


async def _materialize_attachment_paths(
    attachments: list[Attachment],
) -> tuple[dict[int, str], list[str]]:
    """Resolve attachment paths to local files, downloading S3-backed objects when needed."""
    local_paths: dict[int, str] = {}
    temp_paths: list[str] = []

    for attachment in attachments:
        attachment_path = getattr(attachment, "path", None)
        if not attachment_path:
            continue

        local_path = await _resolve_local_attachment_path(attachment_path)
        if not local_path:
            continue

        local_paths[id(attachment)] = local_path

        if local_path != attachment_path:
            temp_paths.append(local_path)

    return local_paths, temp_paths


async def _resolve_local_attachment_path(attachment_path: str) -> str | None:
    """Return a readable local path for an attachment."""
    if Path(attachment_path).is_file():
        return attachment_path

    return await download_s3_object_to_tempfile(attachment_path)
