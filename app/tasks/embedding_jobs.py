"""Background jobs for generating and persisting Gemini image embeddings."""

from app.core.config import settings
from app.core.logger import get_logger
from app.db.session import AsyncSessionLocal
from app.models.attachment import Attachment
from app.models.issue import Issue
from app.repositories.issue_repo import IssueRepository
from app.services.gemini_embedding_service import GeminiEmbeddingService
from app.tasks.image_jobs import _materialize_attachment_paths
from app.utils.s3_utils import delete_temp_files

logger = get_logger("tasks.embedding_jobs")


async def embed_issue_attachments(issue: Issue) -> int:
    """Generate and persist embeddings for each attachment on an issue."""
    if not issue.attachments:
        return 0

    embedded_count = 0
    local_paths, temp_paths = await _materialize_attachment_paths(issue.attachments)

    try:
        attachment: Attachment
        for attachment in issue.attachments:
            local_path = local_paths.get(id(attachment))
            if not local_path:
                logger.warning(
                    "Skipping attachment embedding; no readable path was resolved: "
                    "issue_id=%s attachment_id=%s path=%s",
                    issue.issue_id,
                    getattr(attachment, "attachment_id", None),
                    getattr(attachment, "path", None),
                )
                continue

            if (
                getattr(attachment, "embedding", None) is not None
                and getattr(attachment, "embedding_model", None) == settings.GEMINI_EMBEDDING_MODEL
            ):
                continue

            attachment.embedding = await GeminiEmbeddingService.generate_image_embedding(local_path)
            attachment.embedding_model = settings.GEMINI_EMBEDDING_MODEL
            embedded_count += 1
    finally:
        await delete_temp_files(temp_paths)

    return embedded_count


async def generate_issue_embeddings(issue_id: int) -> None:
    """Load an issue and persist embeddings for its attachments."""
    async with AsyncSessionLocal() as db:
        try:
            issue_repo = IssueRepository(db)
            issue = await issue_repo.get_issue_by_id(issue_id)
            if not issue:
                logger.warning(
                    "Skipping embedding generation; issue not found: issue_id=%s", issue_id
                )
                return

            embedded_count = await embed_issue_attachments(issue)
            await db.commit()

            logger.info(
                "Generated issue attachment embeddings: issue_id=%s issue_label=%s count=%s",
                issue.issue_id,
                issue.issue_label,
                embedded_count,
            )
        except Exception:
            await db.rollback()
            raise
