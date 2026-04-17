"""CLI smoke test for embedding cosine similarity between two issues."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.session import AsyncSessionLocal
from app.repositories.issue_repo import IssueRepository
from app.tasks.image_jobs import get_best_embedding_cosine_match_between_issues

DEFAULT_ISSUE_ID_1 = 32
DEFAULT_ISSUE_ID_2 = 33


def _resolve_issue_ids() -> tuple[int, int]:
    """Return two issue IDs from CLI args or the default pair."""
    args = sys.argv[1:]

    if len(args) == 2:
        return int(args[0]), int(args[1])
    if not args:
        return DEFAULT_ISSUE_ID_1, DEFAULT_ISSUE_ID_2
    raise RuntimeError(
        "Usage: python tests/cli_tests/test_issue_embedding_similarity.py [issue_id_1 issue_id_2]"
    )


async def run_issue_embedding_similarity_smoke_test() -> None:
    """Load two issues from the database and compute best embedding cosine similarity."""
    issue_id_1, issue_id_2 = _resolve_issue_ids()

    async with AsyncSessionLocal() as db:
        issue_repo = IssueRepository(db)
        issue_1 = await issue_repo.get_issue_by_id(issue_id_1)
        issue_2 = await issue_repo.get_issue_by_id(issue_id_2)

    if not issue_1:
        raise RuntimeError(f"Issue not found: {issue_id_1}")
    if not issue_2:
        raise RuntimeError(f"Issue not found: {issue_id_2}")

    result = await get_best_embedding_cosine_match_between_issues(issue_1, issue_2)
    if result is None:
        raise RuntimeError(
            "No comparable attachment embeddings found for the selected issues. "
            "Ensure both issues have attachments with generated embeddings."
        )

    payload = {
        "issue_1": {
            "issue_id": issue_1.issue_id,
            "issue_label": issue_1.issue_label,
        },
        "issue_2": {
            "issue_id": issue_2.issue_id,
            "issue_label": issue_2.issue_label,
        },
        "best_embedding_cosine_similarity": {
            "new_attachment_id": int(result["new_attachment_id"]),
            "old_attachment_id": int(result["old_attachment_id"]),
            "similarity_score": float(result["similarity_score"]),
        },
    }
    print(json.dumps(payload, indent=2))


asyncio.run(run_issue_embedding_similarity_smoke_test())
